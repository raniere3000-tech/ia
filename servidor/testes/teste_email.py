"""Diagnóstico do e-mail no Termux, passo a passo. Não grava a senha em lugar nenhum.

Rodar:  python servidor/testes/teste_email.py
Pergunta o endereço e a senha de app (a senha não aparece na tela), tenta as portas 465 e 587 e diz em que passo cai.
"""
import getpass
import smtplib
import socket
import ssl
from email.message import EmailMessage

de = input('Seu e-mail (o que envia): ').strip()
senha = getpass.getpass('Senha de app (16 letras, sem espaços): ').replace(' ', '')
host = 'smtp.gmail.com'
print(f'\nSenha com {len(senha)} caracteres (tem que ser 16).')
print('Endereços de', host, ':', sorted({a[4][0] for a in socket.getaddrinfo(host, 465)}))

for porta in (465, 587):
    print(f'\n--- porta {porta} ---')
    try:
        if porta == 465:
            s = smtplib.SMTP_SSL(host, porta, timeout=30, context=ssl.create_default_context())
            print('1. conectou (SSL)')
        else:
            s = smtplib.SMTP(host, porta, timeout=30)
            print('1. conectou')
            s.starttls(context=ssl.create_default_context())
            print('2. STARTTLS ok')
        s.login(de, senha)
        print('3. login ok')
        m = EmailMessage()
        m['From'], m['To'], m['Subject'] = de, de, 'Teste EstúdioClip'
        m.set_content('Se você recebeu isto, o envio funciona.')
        s.send_message(m)
        s.quit()
        print('4. e-mail enviado! Olhe a sua caixa de entrada.')
        break
    except smtplib.SMTPAuthenticationError as e:
        print('FALHOU no login: a senha foi recusada.', e.smtp_code)
        print('Crie uma senha de app nova em myaccount.google.com/apppasswords e cole sem espaços.')
        break
    except Exception as e:
        print('FALHOU:', type(e).__name__, e)
else:
    print('\nAs duas portas falharam. Se parou em "1." a rede está bloqueando; tente outro Wi-Fi ou os dados móveis.')
