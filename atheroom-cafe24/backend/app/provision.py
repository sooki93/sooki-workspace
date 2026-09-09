"""Interactive administrator-only provisioning; secrets are never exposed in operator UI."""
import getpass
from cryptography.fernet import Fernet
from app.security import password_hash
if __name__=='__main__':
    password=getpass.getpass('운영자 로그인 비밀번호 (12자 이상): ')
    if len(password)<12: raise SystemExit('12자 이상 입력해주세요.')
    print('OPERATOR_PASSWORD_HASH='+password_hash(password))
    print('TOKEN_ENCRYPTION_KEY='+Fernet.generate_key().decode())
