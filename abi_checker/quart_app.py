import datetime
import asyncio
import json
import os

from quart import Quart, render_template, url_for, websocket
from jinja2 import StrictUndefined
from markupsafe import Markup

from .root import Root
from .report import Report
from .caserun import RunResult
from .compileoptions import CompileOptions

class App(Quart):
    jinja_options = dict(
        autoescape=True,
        line_statement_prefix='%%',
        undefined=StrictUndefined,
    )

app = App(__name__)

def run_url(run):
    return url_for(
        'run',
        case=run.case.tag,
        compile_build=run.compile_build.tag,
        compile_opts=run.compile_options.tag,
        exec_build=run.exec_build.tag,
    )

def run_icon_url(run):
    return url_for(
        'run_icon',
        case=run.case.tag,
        compile_build=run.compile_build.tag,
        compile_opts=run.compile_options.tag,
        exec_build=run.exec_build.tag,
    )

def case_url(case):
    return url_for(
        'case',
        case=case.tag,
    )

@app.context_processor
def jinja_globals():
    return {
        'RunResult': RunResult,
        'run_url': run_url,
        'run_icon_url': run_icon_url,
        'case_url': case_url,
        'asyncio': asyncio,
    }

@app.template_filter(name='include_file')
def include_file(path):
    try:
        return Markup('<pre><code>{}</code></pre>').format(path.read_text())
    except FileNotFoundError:
        return '(no such file)'

@app.template_filter(name='file_info')
def file_info(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return '(no such file)'
    mtime = datetime.datetime.fromtimestamp(stat.st_mtime, datetime.timezone.utc)
    return f'{path.name} modified {mtime}'

root = Root.from_env(os.environ)
report = Report(root)

@app.route('/')
async def index():
    report.get_runs()
    await asyncio.sleep(.01)
    return await render_template("report.html.jinja", report=report)

@app.route('/runs/<case>/<compile_build>/<compile_opts>/<exec_build>/')
async def run(case, compile_build, compile_opts, exec_build):
    run = report.get_run(
        await report.get_case(case),
        await report.get_build(compile_build),
        CompileOptions.parse(compile_opts),
        await report.get_build(exec_build),
    )
    return await render_template("run.html.jinja", run=run)

@app.route('/runs/<case>/<compile_build>/<compile_opts>/<exec_build>/icon/')
async def run_icon(case, compile_build, compile_opts, exec_build):
    run = report.get_run(
        await report.get_case(case),
        await report.get_build(compile_build),
        CompileOptions.parse(compile_opts),
        await report.get_build(exec_build),
    )
    return await render_template("run-icon.html.jinja", run=run)

@app.route('/cases/<case>/')
async def case(case):
    case = await report.get_case(case)
    return await render_template("case.html.jinja", case=case)

@app.websocket('/ws/')
async def ws():
    cancelled = False
    async with asyncio.TaskGroup() as tg:
        while True:
            tag = await websocket.receive()
            case, compile_build, compile_opts, exec_build = tag.split('/')
            run = report.get_run(
                await report.get_case(case),
                await report.get_build(compile_build),
                CompileOptions.parse(compile_opts),
                await report.get_build(exec_build),
            )
            async def respond(run, tag):
                try:
                    await run.get_result()
                finally:
                    await websocket.send(tag)
            tg.create_task(respond(run, tag))
