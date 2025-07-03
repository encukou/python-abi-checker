import os

from quart import Quart, render_template
from jinja2 import StrictUndefined

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

@app.context_processor
def jinja_globals():
    return {
        'RunResult': RunResult,
    }

root = Root.from_env(os.environ)
report = Report(root)

@app.route('/')
async def hello():
    return await render_template("report.html.jinja", report=report)
