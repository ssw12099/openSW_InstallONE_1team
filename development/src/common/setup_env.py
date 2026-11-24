from src.common.config import ROOT
from secrets import token_urlsafe
import os
root = ROOT
out = root / '.env'
if out.exists():
    raise SystemExit('.env already exists; edit it rather than overwrite it.')
s = (root / '.env.example').read_text(encoding="utf-8")
for key in ('client-token','admin-token','signing-key'):
    s = s.replace('replace-'+key,token_urlsafe(40))
fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd,'w',encoding='utf-8') as f: f.write(s)
print('Created .env. Edit PUBLIC_API_BASE.')
