Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
Name "TransferBay"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\TransferBay"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "Feidu.ico"
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\TransferBay.exe"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "SimpChinese"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_OK "TransferBay 需要 64 位 Windows。"
    Abort
  ${EndIf}
  FindWindow $0 "TransferBay.DropWindow.1"
  ${If} $0 != 0
    MessageBox MB_OK "请先从悬浮窗菜单退出正在运行的 TransferBay，再安装。"
    Abort
  ${EndIf}
FunctionEnd

Section
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD}/*"
  CreateShortcut "$SMPROGRAMS\TransferBay.lnk" "$INSTDIR\TransferBay.exe"
  CreateShortcut "$DESKTOP\TransferBay.lnk" "$INSTDIR\TransferBay.exe"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TransferBay" "DisplayName" "TransferBay"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TransferBay" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TransferBay" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\TransferBay.lnk"
  Delete "$DESKTOP\TransferBay.lnk"
  !include "${UNINSTALL_FILES}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\TransferBay"
SectionEnd
