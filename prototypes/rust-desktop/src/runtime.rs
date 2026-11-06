use std::{
    fs::{self, File},
    io::{self, Read, Write},
    net::{Ipv4Addr, SocketAddr, TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

pub struct Runtime {
    pub child: Child,
    pub root: PathBuf,
    pub port: u16,
}

#[cfg(windows)]
static PROCESS_JOB: std::sync::atomic::AtomicPtr<std::ffi::c_void> =
    std::sync::atomic::AtomicPtr::new(std::ptr::null_mut());

// The entire prototype joins a private job BEFORE spawning anything. Descendants
// inherit membership, so a shell crash also closes Python/model/WebView processes.
// Keep the job handle open until OS process teardown; closing it kills this process too.
#[cfg(windows)]
pub fn own_process_tree() -> io::Result<()> {
    use windows_sys::Win32::{
        Foundation::CloseHandle,
        System::{
            JobObjects::{
                AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
                SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
            },
            Threading::GetCurrentProcess,
        },
    };
    unsafe {
        let job = CreateJobObjectW(std::ptr::null(), std::ptr::null());
        if job.is_null() {
            return Err(io::Error::last_os_error());
        }
        let mut limits: JOBOBJECT_EXTENDED_LIMIT_INFORMATION = std::mem::zeroed();
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &limits as *const _ as *const _,
            std::mem::size_of_val(&limits) as u32,
        ) == 0 || AssignProcessToJobObject(job, GetCurrentProcess()) == 0
        {
            let error = io::Error::last_os_error();
            CloseHandle(job);
            return Err(error);
        }
        PROCESS_JOB.store(job, std::sync::atomic::Ordering::SeqCst);
    }
    Ok(())
}

#[cfg(not(windows))]
pub fn own_process_tree() -> io::Result<()> {
    Err(io::Error::other("This prototype requires Windows process ownership"))
}

pub fn fresh_root() -> io::Result<PathBuf> {
    let stamp = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
    let root = std::env::temp_dir().join(format!("rasputin-rust-{}-{stamp}", std::process::id()));
    fs::create_dir(&root)?;
    Ok(root)
}

impl Runtime {
    pub fn start(source: Option<&Path>, backend: Option<&Path>) -> io::Result<Self> {
        let root = fresh_root()?;
        let data = root.join("data");
        fs::create_dir(&data)?;
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0))?;
        let port = listener.local_addr()?.port();
        let mut command = match (source, backend) {
            (Some(source), None) => {
                let source = source.canonicalize()?;
                for file in [".venv/Scripts/python.exe", "server.py", "frontend/index.html"] {
                    if !source.join(file).is_file() {
                        return Err(io::Error::other(format!("Missing source prerequisite: {file}")));
                    }
                }
                let mut command = Command::new(source.join(".venv/Scripts/python.exe"));
                command.arg(source.join("server.py")).current_dir(source);
                command
            }
            (None, Some(backend)) => {
                let backend = backend.canonicalize()?;
                if !backend.is_file() {
                    return Err(io::Error::other("Backend must be an executable file"));
                }
                let mut command = Command::new(&backend);
                command.current_dir(backend.parent().unwrap());
                command
            }
            _ => return Err(io::Error::other("Choose exactly one of --source-root or --backend")),
        };
        command
            .env("HOST", "127.0.0.1")
            .env("PORT", port.to_string())
            .env("RASPUTIN_DATA_DIR", &data)
            .env("RASPUTIN_DESKTOP", "1")
            .env("RASPUTIN_DESKTOP_ONLY", "1")
            .env("RASPUTIN_HTTPS", "0")
            .env("RASPUTIN_LOCALHOST_BYPASS", "0")
            .env("PYTHONUNBUFFERED", "1")
            .env_remove("WRAPPER_RUNTIME")
            .env_remove("RASPUTIN_TLS_CERT_FILE")
            .env_remove("RASPUTIN_TLS_KEY_FILE")
            .stdin(Stdio::null())
            // First-run passwords must never enter benchmark output or logs.
            .stdout(Stdio::null())
            .stderr(Stdio::null());
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            command.creation_flags(0x08000000); // CREATE_NO_WINDOW
        }
        // Free-port selection has a small bind race; never attach to an existing
        // server. Readiness requires our own child to still be alive.
        drop(listener);
        let child = command.spawn()?;
        let runtime = Self { child, root, port };
        fs::write(runtime.root.join("desktop-runtime.json"), serde_json::to_vec_pretty(&serde_json::json!({
            "pid": runtime.child.id(), "ownerPid": std::process::id(),
            "url": runtime.url(), "prototype": true
        }))?)?;
        Ok(runtime)
    }

    pub fn url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }

    pub fn wait_ready(&mut self, timeout: Duration) -> io::Result<()> {
        let deadline = Instant::now() + timeout;
        while Instant::now() < deadline {
            if let Some(status) = self.child.try_wait()? {
                return Err(io::Error::other(format!("Backend exited before readiness: {status}")));
            }
            if listener_is_owned(self.port) && healthy(self.port) && self.child.try_wait()?.is_none() {
                return Ok(());
            }
            thread::sleep(Duration::from_millis(100));
        }
        Err(io::Error::new(io::ErrorKind::TimedOut, "Backend health timed out after 90 seconds"))
    }
}

#[cfg(windows)]
fn listener_pid(port: u16) -> Option<u32> {
    use windows_sys::Win32::NetworkManagement::IpHelper::{
        GetExtendedTcpTable, MIB_TCPROW_OWNER_PID, MIB_TCPTABLE_OWNER_PID,
        TCP_TABLE_OWNER_PID_LISTENER,
    };
    unsafe {
        let mut bytes = 0;
        GetExtendedTcpTable(std::ptr::null_mut(), &mut bytes, 0, 2, TCP_TABLE_OWNER_PID_LISTENER, 0);
        // DWORD-aligned storage for the variable-length Windows table.
        let mut storage = vec![0u32; (bytes as usize).div_ceil(4)];
        if storage.is_empty() || GetExtendedTcpTable(storage.as_mut_ptr().cast(), &mut bytes, 0, 2, TCP_TABLE_OWNER_PID_LISTENER, 0) != 0 {
            return None;
        }
        let table = &*storage.as_ptr().cast::<MIB_TCPTABLE_OWNER_PID>();
        let count = table.dwNumEntries as usize;
        if 4 + count * std::mem::size_of::<MIB_TCPROW_OWNER_PID>() > storage.len() * 4 {
            return None;
        }
        let rows = std::slice::from_raw_parts(table.table.as_ptr(), count);
        rows.iter().find(|row| u16::from_be(row.dwLocalPort as u16) == port)
            .map(|row| row.dwOwningPid)
    }
}

#[cfg(windows)]
fn listener_is_owned(port: u16) -> bool {
    use windows_sys::Win32::{Foundation::CloseHandle, System::{
        JobObjects::IsProcessInJob,
        Threading::{OpenProcess, PROCESS_QUERY_LIMITED_INFORMATION},
    }};
    let Some(pid) = listener_pid(port) else { return false; };
    let job = PROCESS_JOB.load(std::sync::atomic::Ordering::SeqCst);
    if job.is_null() { return false; }
    unsafe {
        let process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid);
        if process.is_null() { return false; }
        let mut owned = 0;
        let success = IsProcessInJob(process, job, &mut owned);
        CloseHandle(process);
        success != 0 && owned != 0
    }
}

#[cfg(not(windows))]
fn listener_is_owned(_port: u16) -> bool { false }

impl Drop for Runtime {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
        let _ = fs::remove_file(self.root.join("desktop-runtime.json"));
        // Files remain under TEMP for inspection; the process job owns any
        // descendants even if child termination or application startup fails.
    }
}

fn healthy(port: u16) -> bool {
    let address = SocketAddr::from((Ipv4Addr::LOCALHOST, port));
    let Ok(mut stream) = TcpStream::connect_timeout(&address, Duration::from_millis(250)) else {
        return false;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_millis(500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(500)));
    if write!(stream, "GET /api/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nConnection: close\r\n\r\n").is_err() {
        return false;
    }
    let mut response = String::new();
    if stream.take(65536).read_to_string(&mut response).is_err() {
        return false;
    }
    response.starts_with("HTTP/1.1 200 ") && response.contains("Rasputin")
}

pub fn write_metrics(root: &Path, value: &serde_json::Value) -> io::Result<()> {
    let mut file = File::create(root.join("startup.json"))?;
    serde_json::to_writer_pretty(&mut file, value)?;
    file.write_all(b"\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn data_roots_are_fresh_and_separate_from_user_data() {
        let first = fresh_root().unwrap();
        let second = fresh_root().unwrap();
        assert_ne!(first, second);
        assert!(first.starts_with(std::env::temp_dir()));
        fs::remove_dir(first).unwrap();
        fs::remove_dir(second).unwrap();
    }

    #[test]
    fn health_rejects_an_unrelated_http_server() {
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
        let port = listener.local_addr().unwrap().port();
        let worker = thread::spawn(move || {
            let (mut stream, _) = listener.accept().unwrap();
            let mut request = [0; 1024];
            stream.read(&mut request).unwrap();
            stream.write_all(b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\nConnection: close\r\n\r\nother").unwrap();
        });
        assert!(!healthy(port));
        worker.join().unwrap();
    }

    #[test]
    #[cfg(windows)]
    fn listener_identity_matches_the_process_that_bound_it() {
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
        assert_eq!(listener_pid(listener.local_addr().unwrap().port()), Some(std::process::id()));
    }
}
