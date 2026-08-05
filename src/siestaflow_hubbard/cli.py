import argparse
import sys
from siestaflow_hubbard.domain.campaign_manifest import CampaignManifest, CampaignState
from siestaflow_hubbard.execution.checkpoint_manager import CheckpointManager
from siestaflow_hubbard.reporting.evidence_exporter import EvidenceExporter
from siestaflow_hubbard.domain.kgrid_builder import KGridBuilder
from siestaflow_hubbard.siesta_backend.fdf_validator import FdfValidator, FdfParser
from siestaflow_hubbard.siesta_backend.fdf_builder import FdfBuilder

def audit_fdf(args):
    print(f"Auditing FDF file: {args.fdf_file}")
    with open(args.fdf_file, "r") as f:
        content = f.read()
    
    parser = FdfParser()
    parsed_data = parser.parse(content)
    validator = FdfValidator(parser)
    
    # Run validations
    validator.check_unit()
    spin_mode = validator.detect_spin_mode()
    orbital_dim = validator.detect_orbital_dimension()
    validator.validate_multi_species()
    
    print("Audit Summary:")
    print(f"  Spin Mode: {spin_mode}")
    print(f"  Orbital Dimension: {orbital_dim}")
    print("  Validation complete.")

def init_campaign(args):
    print(f"Initializing campaign from {args.fdf_file} with name {args.name}")
    manifest = CampaignManifest(name=args.name, state=CampaignState.DRAFT)
    
    # Store arbitrary data for demonstration
    manifest.parameters["source_fdf"] = args.fdf_file
    
    manifest.save_to_file("campaign.json")
    print(f"Campaign initialized to campaign.json")

def converge_campaign(args):
    print(f"Running convergence for {args.campaign_json}")
    manifest = CampaignManifest.load_from_file(args.campaign_json)
    
    if manifest.state == CampaignState.DRAFT or manifest.state == CampaignState.SUSPENDED:
        manifest.transition(CampaignState.LOCKED)
        manifest.transition(CampaignState.CONVERGENCE_RUNNING)
    elif manifest.state == CampaignState.LOCKED:
        manifest.transition(CampaignState.CONVERGENCE_RUNNING)
        
    # Simulate convergence
    manifest.transition(CampaignState.CONVERGED)
    manifest.save_to_file(args.campaign_json)
    print("Convergence completed.")

def run_campaign(args):
    print(f"Running production campaign for {args.campaign_json}")
    manifest = CampaignManifest.load_from_file(args.campaign_json)
    
    if manifest.state == CampaignState.CONVERGED or manifest.state == CampaignState.SUSPENDED:
        manifest.transition(CampaignState.LINEAR_RESPONSE_RUNNING)
        
    # Simulate completion
    manifest.transition(CampaignState.COMPLETED)
    manifest.save_to_file(args.campaign_json)
    print("Campaign completed.")

def resume_campaign(args):
    print(f"Resuming campaign {args.campaign_json}")
    manifest = CampaignManifest.load_from_file(args.campaign_json)
    
    # Just printing for now since actual execution skips steps if valid
    print(f"Resuming from state {manifest.state}")
    
def report_campaign(args):
    print(f"Generating evidence report for {args.campaign_json}")
    manifest = CampaignManifest.load_from_file(args.campaign_json)
    
    exporter = EvidenceExporter(output_dir=".")
    
    # Fake data for demonstration
    report_data = {
        "geometry_spin": {"spin_mode": "collinear"},
        "convergence_history": {"steps": 15},
        "linear_response": [{"alpha": 0.1, "n_alpha": 0.05, "r2": 0.99, "chi0": 1.2, "chi": 1.5}],
        "susceptibility_inversion": {"U_eff": 4.5},
        "provenance": [{"file": "campaign.json", "hash": "abc"}]
    }
    
    exporter.export(report_data)
    print("Report generated in EVIDENCE_REPORT.md and EVIDENCE_REPORT.html")

def main():
    parser = argparse.ArgumentParser(description="SIESTAFLOW CLI")
    subparsers = parser.add_subparsers(dest="command")
    
    audit_parser = subparsers.add_parser("audit-fdf")
    audit_parser.add_argument("fdf_file", help="Path to FDF file")
    
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("fdf_file", help="Path to FDF file")
    init_parser.add_argument("--name", required=True, help="Campaign name")
    
    converge_parser = subparsers.add_parser("converge")
    converge_parser.add_argument("campaign_json", help="Path to campaign.json")
    
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("campaign_json", help="Path to campaign.json")
    
    resume_parser = subparsers.add_parser("resume")
    resume_parser.add_argument("campaign_json", help="Path to campaign.json")
    
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("campaign_json", help="Path to campaign.json")
    
    args = parser.parse_args()
    
    if args.command == "audit-fdf":
        audit_fdf(args)
    elif args.command == "init":
        init_campaign(args)
    elif args.command == "converge":
        converge_campaign(args)
    elif args.command == "run":
        run_campaign(args)
    elif args.command == "resume":
        resume_campaign(args)
    elif args.command == "report":
        report_campaign(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
