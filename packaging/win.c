#define UNICODE
#include <windows.h>
#include <wchar.h>
int WINAPI wWinMain(HINSTANCE a,HINSTANCE b,LPWSTR c,int d){
 wchar_t dir[32768],exe[32768],cmd[]=L"pythonw.exe desktop.pyw";
 if (!GetModuleFileNameW(NULL,dir,32768)) return 1;
 wchar_t *end=wcsrchr(dir,L'\\'); if(!end)return 1;
 wcscpy(end,L"\\runtime"); swprintf(exe,32768,L"%ls\\pythonw.exe",dir);
 STARTUPINFOW si={sizeof(si)}; PROCESS_INFORMATION pi={0};
 if(!CreateProcessW(exe,cmd,NULL,NULL,FALSE,0,NULL,dir,&si,&pi)){MessageBoxW(NULL,L"请完整解压压缩包后再启动 TransferBay。",L"TransferBay",MB_OK);return 1;}CloseHandle(pi.hThread);CloseHandle(pi.hProcess);return 0;
}
