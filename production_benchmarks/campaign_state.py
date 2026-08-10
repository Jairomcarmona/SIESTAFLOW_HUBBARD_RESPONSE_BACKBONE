import json
import os

class CampaignState:
    def __init__(self):
        self.completed = set()
        self.failed = {}
        self.reference_dm_sha256 = ""
        self.current_dag_node = ""
        self.material_statuses = {}
    def mark_complete(self, key, result_dict): pass
    def mark_failed(self, key, err): pass
    def is_complete(self, key): return False
    def save(self): pass
    def load(self): pass

def resume_incomplete(campaign_dir):
    return []
