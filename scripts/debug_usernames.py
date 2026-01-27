from backend.app.honeypot.tokens import HoneytokenGenerator

gen = HoneytokenGenerator()
for service_type in ['database', 'api', 'backup', 'monitoring']:
    cred = gen.generate_credentials(service_type)
    print(f'{service_type}: {cred["username"]}')
