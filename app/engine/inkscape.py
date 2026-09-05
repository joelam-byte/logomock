"""Inkscape CLI boundary: finite timeouts, unique outputs, verified success."""
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from app.config import configured_inkscape_path
from app.engine.base import EngineError
from app.engine.registry import find_inkscape_from_registry
from app.services.errors import CONVERT_FAILED, ENGINE_NOT_FOUND


class InkscapeEngine:
    def __init__(self,exe=None):
        self._exe=Path(exe) if exe and Path(exe).is_file() else self._discover()

    @staticmethod
    def _discover():
        for candidate in (configured_inkscape_path(), find_inkscape_from_registry(),shutil.which('inkscape')):
            if candidate and Path(candidate).is_file():
                return Path(candidate)
        for drive in ('C','D'):
            for base in ('Program Files','Program Files (x86)'):
                for suffix in ('bin/inkscape.exe','inkscape.exe'):
                    candidate=Path(f'{drive}:/{base}/Inkscape')/suffix
                    if candidate.is_file():
                        return candidate
        return None

    def available(self):
        return bool(self._exe and self._exe.is_file())

    def version(self):
        if not self.available():
            return ''
        output=self._execute(['--version']).stdout.strip()
        return output

    def _execute(self,args):
        if not self.available():
            raise EngineError(ENGINE_NOT_FOUND,'未找到 Inkscape，请在设置中选择 Inkscape 安装目录下的 bin/inkscape.exe')
        executable=self._exe
        if os.name=='nt' and self._exe.with_suffix('.com').is_file():
            executable=self._exe.with_suffix('.com')
        try:
            return subprocess.run([str(executable),*map(str,args)],capture_output=True,text=True,
                                  encoding='utf-8',errors='replace',timeout=120,
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise EngineError(CONVERT_FAILED,f'矢量引擎执行失败或超时：{exc}') from exc

    def _export(self,source,destination,kind,extra=()):
        target=Path(destination)
        target.parent.mkdir(parents=True,exist_ok=True)
        temporary=target.with_name(f'.{target.stem}-{uuid.uuid4().hex}.{kind}')
        try:
            process=self._execute([str(Path(source).resolve()),f'--export-type={kind}',f'--export-filename={temporary.resolve()}',*extra])
            if process.returncode!=0 or not temporary.is_file() or temporary.stat().st_size==0:
                raise EngineError(CONVERT_FAILED,f'{kind.upper()} 转换失败',stderr=process.stderr.strip())
            header=temporary.read_bytes()[:100].lstrip()
            valid=(header.startswith(bytes([137,80,78,71])) if kind=='png' else header.startswith(b'%PDF') if kind=='pdf' else b'<' in header)
            if not valid:
                raise EngineError(CONVERT_FAILED,'转换产物格式不正确',stderr=process.stderr.strip())
            os.replace(temporary,target)
        finally:
            temporary.unlink(missing_ok=True)

    def to_svg(self,src,svg):
        self._export(src,svg,'svg')

    def to_svg_page(self,src,svg,page_number):
        if page_number < 1:
            raise ValueError('PDF 页码从 1 开始')
        failures=[]
        for flag in (f'--pages={page_number}',f'--pdf-page={page_number}'):
            try:
                self._export(src,svg,'svg',(flag,))
                return
            except EngineError as exc:
                failures.append(exc.stderr or exc.message)
        raise EngineError(CONVERT_FAILED,f'无法读取第 {page_number} 页',stderr='\n'.join(failures))

    def svg_to_pdf(self,svg,pdf,*,text_to_path=True):
        self._export(svg,pdf,'pdf',['--export-text-to-path'] if text_to_path else [])

    def svg_to_png(self,svg,png,*,width=None):
        extras=['--export-background-opacity=0']
        if width:
            extras.append(f'--export-width={max(1,min(4096,round(width)))}')
        self._export(svg,png,'png',extras)

    def query_all(self,svg):
        process=self._execute([str(Path(svg).resolve()),'--query-all'])
        if process.returncode!=0:
            raise EngineError(CONVERT_FAILED,'无法分析 SVG 对象边界',stderr=process.stderr.strip())
        boxes={}
        for line in process.stdout.splitlines():
            parts=line.rsplit(',',4)
            if len(parts)!=5:
                continue
            try:
                box=tuple(float(value) for value in parts[1:])
            except ValueError:
                continue
            if all(__import__('math').isfinite(v) for v in box) and box[2]>=0 and box[3]>=0:
                boxes[parts[0]]=box
        if not boxes:
            raise EngineError(CONVERT_FAILED,'文件没有可识别的矢量图形',stderr=process.stderr.strip())
        return boxes
