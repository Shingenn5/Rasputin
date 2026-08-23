!macro customInstall
  ; Electron's Windows GPU sandbox needs read/execute access for the
  ; ALL RESTRICTED APPLICATION PACKAGES AppContainer group. This is required
  ; on systems whose inherited ACL contains orphaned AppContainer SIDs.
  ExecWait '"$SYSDIR\icacls.exe" "$INSTDIR" /grant "*S-1-15-2-2:(OI)(CI)(RX)" /T' $0
  StrCmp $0 "0" acl_done
  MessageBox MB_ICONSTOP|MB_OK "Rasputin could not configure the Windows sandbox permissions for its install folder. The installation was not completed."
  Abort
acl_done:
!macroend
