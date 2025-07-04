import datetime
import os

from quart import Quart, render_template, url_for
from jinja2 import StrictUndefined
from markupsafe import Markup

from .root import Root
from .report import Report
from .caserun import RunResult

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
        'case_url': case_url,
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
    return await render_template("report.html.jinja", report=report)

@app.route('/runs/<case>/<compile_build>/<exec_build>')
async def run(case, compile_build, exec_build):
    run = report.get_run(
        await report.get_case(case),
        await report.get_build(compile_build),
        await report.get_build(exec_build),
    )
    return await render_template("run.html.jinja", run=run)

@app.route('/cases/<case>')
async def case(case):
    case = await report.get_case(case)
    return await render_template("case.html.jinja", case=case)
