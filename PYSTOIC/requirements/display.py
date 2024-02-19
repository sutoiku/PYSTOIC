import sh
import json
from .utils import Requirement, is_wb_req
import tabulate


def _requirements() -> list[Requirement]:
    dcts: list[dict] = json.loads(sh.pip("list", "--format=json"))
    return [Requirement(**dct) for dct in dcts]


def requirements_table(wb_prefix: str = "index", tablefmt: str = "html", **kwargs):
    requirements = _requirements()
    table_headers = ["Name", "Version"]
    wb_reqs = [req for req in requirements if is_wb_req(str(req), wb_prefix)]
    other_reqs = [req for req in requirements if not is_wb_req(str(req), wb_prefix)]
    all_reqs = sorted(wb_reqs, key=lambda req: req.name) + sorted(other_reqs, key=lambda req: req.name)
    table_data = [[req.name, req.version] for req in all_reqs]
    return tabulate.tabulate(table_data, headers=table_headers, tablefmt=tablefmt, **kwargs)
