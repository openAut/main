"""Run boundary checks in a disposable PostgreSQL database, never the application database."""
import argparse
from pathlib import Path
import shlex
import subprocess
import time
import uuid


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True,help='Already-local PostgreSQL 16-compatible image; pulling is disabled')
    parser.add_argument('--ssh-host',help='Optional SSH alias for a Docker test host')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    name='openaut-discovery-test-'+uuid.uuid4().hex[:12]
    def target(command):
        return ['ssh','-o','BatchMode=yes',args.ssh_host,shlex.join(command)] if args.ssh_host else command
    def run(command,data=None):
        result=subprocess.run(target(command),input=data,capture_output=True,text=True,encoding='utf-8',timeout=90)
        if result.returncode:
            raise RuntimeError(result.stderr)  # Only synthetic, credential-free fixtures run here.
        return result.stdout
    try:
        run(['docker','run','--pull=never','-d','--name',name,'--network=none','--memory=256m',
             '--tmpfs','/var/lib/postgresql/data:rw,size=256m','-e','POSTGRES_HOST_AUTH_METHOD=trust',args.image])
        for _ in range(60):
            if subprocess.run(target(['docker','exec',name,'pg_isready','-h','127.0.0.1','-U','postgres']),capture_output=True,timeout=15).returncode==0:
                break
            time.sleep(1)
        else: raise RuntimeError('test_database_not_ready')
        run(['docker','exec',name,'createdb','-U','postgres','openaut'])
        def sql(text):
            return run(['docker','exec','-i',name,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d','openaut'],text)
        sql('''CREATE SCHEMA system; CREATE SCHEMA telemetry;
CREATE TABLE system.sites(site text PRIMARY KEY);
CREATE TABLE system.devices(node text PRIMARY KEY);
CREATE TABLE telemetry.readings(ts timestamptz,site text,node text,system text,metric text,value double precision,bool_val boolean,unit text);''')
        for path in (root.parent/'platform-poc2/db/001-system.sql',root/'schema.sql',root/'test-database.sql'):
            output=sql(path.read_text(encoding='utf-8'))
        assert 'PORTABLE_DISCOVERY_DATABASE_TESTS_PASS' in output
        print('PORTABLE_DISCOVERY_DATABASE_TESTS_PASS')
    finally:
        subprocess.run(target(['docker','rm','-f',name]),capture_output=True,timeout=30)


if __name__=='__main__':
    main()
