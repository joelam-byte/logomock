"""Desktop launcher: bundled runtime, loopback server, small local control window."""
import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from queue import Empty


def prepare_runtime(folder):
    (folder/'projects').mkdir(parents=True,exist_ok=True)
    if getattr(sys,'frozen',False):
        # A one-folder PyInstaller build stores Tcl/Tk beside the executable,
        # while the bootloader's temporary module location does not contain it.
        # Override the runtime hook value so the launcher can create its control
        # window (and therefore the native Save As window).
        bundled=Path(sys.executable).resolve().parent/'_internal'
        tcl=bundled/'_tcl_data'
        tk=bundled/'_tk_data'
        if (tcl/'init.tcl').is_file() and (tk/'tk.tcl').is_file():
            os.environ['TCL_LIBRARY']=str(tcl)
            os.environ['TK_LIBRARY']=str(tk)
        return
    # Development fallback for a Conda Tcl installation inaccessible to Tcl's
    # own file loader. Frozen builds use PyInstaller's collected runtime hook.
    if not getattr(sys,'frozen',False):
        runtime=Path(__file__).resolve().parent/'tools'/'tk-runtime'
        for key,relative in [('TCL_LIBRARY','tcl8.6'),('TK_LIBRARY','tk8.6')]:
            if (runtime/relative).is_dir():
                os.environ.setdefault(key,str(runtime/relative))


def data_folder(explicit=None):
    default=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    return Path(explicit or os.environ.get('LOGOMOCK_DATA_DIR') or default).resolve()


def existing_url(folder):
    try:
        meta=json.loads((folder/'.runtime.json').read_text(encoding='utf-8'))
        port=int(meta['port'])
        if not 1<=port<=65535:
            return None
        url=f'http://127.0.0.1:{port}'
        with urllib.request.urlopen(url+'/api/health',timeout=1) as response:
            health=json.load(response)
        if health.get('ok') and Path(health['data']['data_dir']).resolve()==folder:
            return url
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return None


def main():
    parser=argparse.ArgumentParser(description='LogoMock local workstation')
    parser.add_argument('--data-dir')
    parser.add_argument('--headless',action='store_true',help='Serve without opening browser/control window')
    parser.add_argument('--port',type=int,default=0)
    args=parser.parse_args()
    folder=data_folder(args.data_dir)
    prepare_runtime(folder)
    prior=existing_url(folder)
    if prior and not args.headless:
        webbrowser.open(prior)
        return
    os.environ['LOGOMOCK_DATA_DIR']=str(folder)
    os.environ.pop('LOGOMOCK_OPEN_BROWSER',None)
    # Allocate the actual listening socket before starting Uvicorn: no port race.
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.bind(('127.0.0.1',args.port))
    sock.listen(128)
    port=sock.getsockname()[1]
    os.environ['LOGOMOCK_PORT']=str(port)
    from app.main import app
    from app.routers.project import atomic_write_json
    import uvicorn
    log_path=folder/'logomock.log'
    # Windowed EXE has no stdout/stderr; Uvicorn must not format a missing stream.
    log=log_path.open('a',encoding='utf-8',buffering=1)
    if sys.stdout is None:
        sys.stdout=log
    if sys.stderr is None:
        sys.stderr=log
    config=uvicorn.Config(app,host='127.0.0.1',port=port,access_log=False,log_level='warning',log_config=None)
    server=uvicorn.Server(config)
    url=f'http://127.0.0.1:{port}'
    atomic_write_json(folder/'.runtime.json',dict(port=port,pid=os.getpid()))
    if args.headless:
        print(url,flush=True)
        server.run(sockets=[sock])
        return
    worker=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True)
    worker.start()
    import tkinter as tk
    from tkinter import messagebox
    from app.services import save_dialog
    root=tk.Tk()
    root.title('LogoMock · 本地工作台')
    root.geometry('470x260')
    root.resizable(False,False)
    root.configure(bg='#f5f7f3')
    tk.Label(root,text='LogoMock',font=('Segoe UI',23,'bold'),fg='#2b6954',bg='#f5f7f3').pack(pady=(20,4))
    status=tk.StringVar(value='正在启动本地工作台…')
    tk.Label(root,textvariable=status,font=('Microsoft YaHei UI',10),bg='#f5f7f3').pack(pady=5)
    tk.Label(root,text='关闭此窗口将停止本地服务。\n图片和项目只保存在本机。',font=('Microsoft YaHei UI',9),fg='#66756c',bg='#f5f7f3').pack(pady=8)
    buttons=tk.Frame(root,bg='#f5f7f3')
    buttons.pack(pady=10)
    tk.Button(buttons,text='打开工作台',command=lambda:webbrowser.open(url),width=15).pack(side='left',padx=5)
    tk.Button(buttons,text='打开项目目录',command=lambda:os.startfile(folder/'projects'),width=15).pack(side='left',padx=5)
    save_broker=save_dialog.SaveDialogBroker()
    save_dialog.configure_broker(save_broker)

    def service_save_dialog_requests():
        while True:
            try:
                request=save_broker.next_request(timeout=0)
            except Empty:
                break
            try:
                print('[save-dialog] desktop thread received request',flush=True)
                destination=save_dialog.show_png_destination(root,request.initial_name)
            except Exception as exc:
                save_broker.reject(request,exc)
            else:
                print('[save-dialog] native dialog closed',flush=True)
                save_broker.resolve(request,destination)
        root.after(80,service_save_dialog_requests)

    def ready():
        if server.started:
            status.set('工作台运行中 · '+url)
            webbrowser.open(url)
        elif not worker.is_alive():
            status.set('启动失败，请查看 logomock.log')
        else:
            root.after(200,ready)

    def close():
        if messagebox.askokcancel('退出 LogoMock','请确认编辑已保存、导出已完成，再退出工作台。'):
            server.should_exit=True
            root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    root.after(100,ready)
    root.after(80,service_save_dialog_requests)
    root.mainloop()
    save_dialog.configure_broker(None)
    worker.join(timeout=3)
    sock.close()
    log.close()


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        import traceback
        try:
            folder=data_folder()
            with (folder/'startup-error.log').open('a',encoding='utf-8') as file:
                traceback.print_exc(file=file)
            import tkinter.messagebox
            tkinter.messagebox.showerror('LogoMock 无法启动',str(exc)+'\n请查看 startup-error.log')
        except Exception:
            pass
        raise
