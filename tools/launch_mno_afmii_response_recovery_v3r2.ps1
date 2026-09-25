$ErrorActionPreference = 'Stop'
$workspace = 'C:\Users\Jairo\Downloads\SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0'
$wslCommand = "cd /mnt/c/Users/Jairo/Downloads/SIESTAFLOW_HUBBARD_RESPONSE_BACKBONE_V0_1_0 && .codex_terra_full_wheel_validation2/bin/python tools/launch_mno_afmii_response_recovery_v3r2.py > campaigns/mno_afmii_strict_lr_v3r2/results/response-matrix-foreground-recovery-v3-launch.log 2>&1"
Start-Process -FilePath 'wsl.exe' -ArgumentList @('-d','Ubuntu','--','bash','-lc',$wslCommand) -WindowStyle Hidden
