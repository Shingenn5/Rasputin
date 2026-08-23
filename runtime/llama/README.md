# Native llama.cpp runtime manifest

The manifest pins the Windows llama.cpp CPU and CUDA builds used by the desktop
installer. The prepare-desktop-runtime.ps1 build step downloads and verifies
those assets at build time, flattens each verified runtime into bundled/, and
runs llama-server --version before electron-builder packages the application.

The shipped Windows installer therefore contains the native inference engine;
an end user does not install Docker, Python, Node, or llama.cpp separately.
Model weights remain user-selected downloads from the model catalog.

The manifest is also retained for runtime identity and compatibility selection.
Development checkouts may still use the repository's native Python launch path,
but the packaged Electron application resolves its engine exclusively from the
bundled runtime directory.
