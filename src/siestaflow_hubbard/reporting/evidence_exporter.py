import os
import json
from typing import Dict, Any

class EvidenceExporter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def _generate_markdown(self, data: Dict[str, Any]) -> str:
        md = "# SIESTAFLOW Evidence Report\n\n"
        
        md += "## Geometry & Spin Audit\n"
        md += "```json\n"
        md += json.dumps(data.get("geometry_spin", {}), indent=2)
        md += "\n```\n\n"
        
        md += "## Convergence History\n"
        md += "```json\n"
        md += json.dumps(data.get("convergence_history", {}), indent=2)
        md += "\n```\n\n"
        
        md += "## Linear Response Regression\n"
        md += "| Alpha | n(alpha) | R^2 | chi0 | chi |\n"
        md += "|---|---|---|---|---|\n"
        for row in data.get("linear_response", []):
            md += f"| {row.get('alpha')} | {row.get('n_alpha')} | {row.get('r2')} | {row.get('chi0')} | {row.get('chi')} |\n"
        md += "\n"
        
        md += "## Susceptibility Inversion Matrix & U_eff\n"
        md += "```json\n"
        md += json.dumps(data.get("susceptibility_inversion", {}), indent=2)
        md += "\n```\n\n"
        
        md += "## Cryptographic Provenance\n"
        md += "| File | SHA-256 Hash |\n"
        md += "|---|---|\n"
        for item in data.get("provenance", []):
            md += f"| {item.get('file')} | {item.get('hash')} |\n"
            
        return md

    def _generate_html(self, data: Dict[str, Any]) -> str:
        html = "<!DOCTYPE html>\n<html>\n<head>\n<title>SIESTAFLOW Evidence Report</title>\n"
        html += "<style>body { font-family: sans-serif; margin: 40px; } table { border-collapse: collapse; width: 100%; } th, td { border: 1px solid #ddd; padding: 8px; } th { background-color: #f2f2f2; }</style>\n"
        html += "</head>\n<body>\n"
        
        html += "<h1>SIESTAFLOW Evidence Report</h1>\n"
        
        html += "<h2>Geometry & Spin Audit</h2>\n<pre>"
        html += json.dumps(data.get("geometry_spin", {}), indent=2)
        html += "</pre>\n"
        
        html += "<h2>Convergence History</h2>\n<pre>"
        html += json.dumps(data.get("convergence_history", {}), indent=2)
        html += "</pre>\n"
        
        html += "<h2>Linear Response Regression</h2>\n"
        html += "<table>\n<tr><th>Alpha</th><th>n(alpha)</th><th>R^2</th><th>chi0</th><th>chi</th></tr>\n"
        for row in data.get("linear_response", []):
            html += f"<tr><td>{row.get('alpha')}</td><td>{row.get('n_alpha')}</td><td>{row.get('r2')}</td><td>{row.get('chi0')}</td><td>{row.get('chi')}</td></tr>\n"
        html += "</table>\n"
        
        html += "<h2>Susceptibility Inversion Matrix & U_eff</h2>\n<pre>"
        html += json.dumps(data.get("susceptibility_inversion", {}), indent=2)
        html += "</pre>\n"
        
        html += "<h2>Cryptographic Provenance</h2>\n"
        html += "<table>\n<tr><th>File</th><th>SHA-256 Hash</th></tr>\n"
        for item in data.get("provenance", []):
            html += f"<tr><td>{item.get('file')}</td><td>{item.get('hash')}</td></tr>\n"
        html += "</table>\n"
        
        html += "</body>\n</html>"
        return html

    def export(self, data: Dict[str, Any]):
        md_content = self._generate_markdown(data)
        with open(os.path.join(self.output_dir, "EVIDENCE_REPORT.md"), "w") as f:
            f.write(md_content)
            
        html_content = self._generate_html(data)
        with open(os.path.join(self.output_dir, "EVIDENCE_REPORT.html"), "w") as f:
            f.write(html_content)
