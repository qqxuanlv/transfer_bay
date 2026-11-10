#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shellapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <wchar.h>

static HWND win;static int scale=96;static HFONT hTitle,hSub;
static WCHAR label[128]=L"等待配对";static int mode=0;static wchar_t classname[]=L"TransferBay.DropWindow.1";
enum {UPDATE=WM_APP+1,REOPEN,ENDPIPE};
static int px(int x){return MulDiv(x,scale,96);}
static void event(const char *s){puts(s);fflush(stdout);}
static DWORD WINAPI reader(void *arg){
 char buf[2048];while(fgets(buf,sizeof(buf),stdin)){
   buf[strcspn(buf,"\r\n")]=0;
   wchar_t *p=calloc(strlen(buf)+2,sizeof(wchar_t));if(!p)continue;
   MultiByteToWideChar(CP_UTF8,0,buf,-1,p,(int)strlen(buf)+1);
   if(!PostMessageW(win,UPDATE,0,(LPARAM)p))free(p);
 }PostMessageW(win,ENDPIPE,0,0);return 0;
}
static void menu(HWND w){
 HMENU m=CreatePopupMenu();AppendMenuW(m,MF_STRING,1,L"打开 TransferBay");AppendMenuW(m,MF_STRING,2,L"隐藏悬浮窗");AppendMenuW(m,MF_SEPARATOR,0,NULL);AppendMenuW(m,MF_STRING,3,L"退出 TransferBay");
 POINT p;GetCursorPos(&p);SetForegroundWindow(w);int id=TrackPopupMenu(m,TPM_RETURNCMD|TPM_RIGHTBUTTON,p.x,p.y,0,w,NULL);DestroyMenu(m);
 if(id==1)event("OPEN");else if(id==2)event("HIDE");else if(id==3)event("QUIT");
}
static LRESULT CALLBACK proc(HWND w,UINT msg,WPARAM a,LPARAM b){
 switch(msg){
 case WM_CREATE:DragAcceptFiles(w,TRUE);return 0;
 case WM_NCHITTEST:return HTCAPTION;
 case WM_NCLBUTTONDBLCLK:event("OPEN");return 0;
 case WM_NCRBUTTONUP:case WM_CONTEXTMENU:menu(w);return 0;
 case REOPEN:event("OPEN");return 0;
 case WM_DROPFILES:{
   HDROP d=(HDROP)a;UINT count=DragQueryFileW(d,0xffffffff,NULL,0);if(count>100){event("LIMIT");DragFinish(d);return 0;}
   fputs("DROP",stdout);
   for(UINT i=0;i<count;i++){
     UINT len=DragQueryFileW(d,i,NULL,0)+1;WCHAR *p=calloc(len,sizeof(WCHAR));if(!p)continue;DragQueryFileW(d,i,p,len);
     int n=WideCharToMultiByte(CP_UTF8,0,p,-1,NULL,0,NULL,NULL);char *s=malloc(n);
     if(s){WideCharToMultiByte(CP_UTF8,0,p,-1,s,n,NULL,NULL);putchar('\t');fputs(s,stdout);free(s);}free(p);
   }putchar('\n');fflush(stdout);DragFinish(d);return 0;
 }
 case UPDATE:{
   wchar_t *p=(wchar_t*)b;int visible=p[0]==L'1';mode=p[1]-L'0';wcsncpy(label,p+2,127);label[127]=0;free(p);
   if(visible!=!!IsWindowVisible(w))ShowWindow(w,visible?SW_SHOWNOACTIVATE:SW_HIDE);
   InvalidateRect(w,NULL,FALSE);return 0;
 }
 case WM_PAINT:{
   PAINTSTRUCT ps;HDC dc=BeginPaint(w,&ps);RECT r;GetClientRect(w,&r);
   HBRUSH bg=CreateSolidBrush(RGB(47,42,58));FillRect(dc,&r,bg);DeleteObject(bg);SetBkMode(dc,TRANSPARENT);
   POINT plane[4]={{px(8),px(19)},{px(26),px(12)},{px(19),px(30)},{px(16),px(22)}};HBRUSH ink=CreateSolidBrush(mode==1?RGB(167,225,198):RGB(208,195,231));HGDIOBJ ob=SelectObject(dc,ink),op=SelectObject(dc,GetStockObject(NULL_PEN));Polygon(dc,plane,4);SelectObject(dc,ob);SelectObject(dc,op);DeleteObject(ink);
   RECT top={px(33),px(3),r.right-px(4),px(22)},sub={px(33),px(22),r.right-px(4),r.bottom};
   HGDIOBJ of=SelectObject(dc,hTitle);SetTextColor(dc,RGB(255,253,255));DrawTextW(dc,L"TransferBay",-1,&top,DT_LEFT|DT_VCENTER|DT_SINGLELINE|DT_NOPREFIX);
   SelectObject(dc,hSub);SetTextColor(dc,RGB(223,214,231));DrawTextW(dc,label,-1,&sub,DT_LEFT|DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);SelectObject(dc,of);EndPaint(w,&ps);return 0;
 }
 case WM_ERASEBKGND:return 1;
 case WM_CLOSE:event("HIDE");return 0;
 case ENDPIPE:DestroyWindow(w);return 0;
 case WM_DESTROY:PostQuitMessage(0);return 0;
 }return DefWindowProcW(w,msg,a,b);
}
int WINAPI wWinMain(HINSTANCE inst,HINSTANCE prev,LPWSTR args,int show){
 SetProcessDPIAware();HDC dc=GetDC(NULL);scale=GetDeviceCaps(dc,LOGPIXELSX);ReleaseDC(NULL,dc);
 hTitle=CreateFontW(-px(13),0,0,0,FW_SEMIBOLD,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
 hSub=CreateFontW(-px(11),0,0,0,FW_NORMAL,0,0,0,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Microsoft YaHei UI");
 WNDCLASSW wc={0};wc.style=CS_DBLCLKS;wc.lpfnWndProc=proc;wc.hInstance=inst;wc.hCursor=LoadCursor(NULL,IDC_ARROW);wc.lpszClassName=classname;RegisterClassW(&wc);
 RECT work={0};SystemParametersInfoW(SPI_GETWORKAREA,0,&work,0);int wid=px(122),ht=px(43);
 win=CreateWindowExW(WS_EX_TOOLWINDOW|WS_EX_TOPMOST|WS_EX_NOACTIVATE|WS_EX_ACCEPTFILES,classname,L"TransferBay 文件投递",WS_POPUP,work.right-wid-px(16),work.top+px(110),wid,ht,NULL,NULL,inst,NULL);if(!win)return 1;
 SetWindowRgn(win,CreateRoundRectRgn(0,0,wid+1,ht+1,px(14),px(14)),TRUE);ShowWindow(win,SW_SHOWNOACTIVATE);
 HANDLE t=CreateThread(NULL,0,reader,NULL,0,NULL);if(t)CloseHandle(t);
 MSG m;while(GetMessageW(&m,NULL,0,0)>0){TranslateMessage(&m);DispatchMessageW(&m);}DeleteObject(hTitle);DeleteObject(hSub);return 0;
}
