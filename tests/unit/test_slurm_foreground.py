from siestaflow_hubbard.execution.slurm_foreground import FOREGROUND_EXPORT, four_rank_foreground_command


def test_four_rank_campaign_submission_is_blocking_and_single_threaded():
    command = four_rank_foreground_command("echo worker")
    assert command[:4] == ["sbatch", "--wait", "--no-requeue", "--parsable"]
    assert FOREGROUND_EXPORT in command
    assert command[command.index("-n") + 1] == "4"
    assert command[command.index("-c") + 1] == "1"
