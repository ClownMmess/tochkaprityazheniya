import shutil
import subprocess
import sys

required={'docker':['docker','compose','version'],'ollama':['ollama','--version'],'cloudflared':['cloudflared','--version']}
failed=False
for name,args in required.items():
    if not shutil.which(name):
        print(f'MISSING: {name}');failed=True;continue
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=15)
        print(f'{name}: '+('OK' if result.returncode==0 else 'FAILED'))
        failed=failed or result.returncode!=0
    except subprocess.TimeoutExpired: print(f'{name}: TIMEOUT');failed=True
print('Python:',sys.version.split()[0])
raise SystemExit(1 if failed else 0)
