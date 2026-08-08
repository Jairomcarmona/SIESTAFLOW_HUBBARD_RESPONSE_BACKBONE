import os
import re

test_dir = "tests"

imports = "from siestaflow_hubbard.domain.semantic_validation import SemanticValidator\nfrom siestaflow_hubbard.domain.campaign_manifest import CampaignManifest\n"

for root, _, files in os.walk(test_dir):
    for file in files:
        if file.startswith("test_") and file.endswith(".py"):
            filepath = os.path.join(root, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if "SemanticValidator" in content and "from siestaflow_hubbard.domain.semantic_validation" not in content:
                content = imports + content
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Added imports to {filepath}")
