from cryptography.fernet import Fernet
import sqlite3
import base64

def test_cryptography1():
    # key = Fernet.generate_key()
    key = b'lFZT2MQAFbJkTaS1SJPCXDz6C7lsEcw41aEq-oJGz-I='
    print(key)
    cipher = Fernet(key)
    plaintext = ""
    encrypted = cipher.encrypt(plaintext.encode())

    # 存储加密数据
    conn = sqlite3.connect("my_secure.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS secure (id INTEGER, data BLOB)")
    c.execute("INSERT INTO secure (id, data) VALUES (?, ?)", (1, encrypted))
    conn.commit()

    c.execute("SELECT data FROM secure WHERE id = 1")
    encrypted_data = c.fetchone()[0]
    decrypted = cipher.decrypt(encrypted_data).decode()
    print("Decrypted:", decrypted)

def test_cryptography2():
    raw_key = b"1234567890abcdef1234567890abcdef"  # 必须是 32 字节
    encoded_key = base64.urlsafe_b64encode(raw_key)
    print("Base64 Encoded Key:", encoded_key.decode())
    # key = Fernet.generate_key()
    # key = b'lFZT2MQAFbJkTaS1SJPCXDz6C7lsEcw41aEq-oJGz-I='
    # print(key)
    cipher = Fernet(encoded_key)

    plaintext = ""
    encrypted = cipher.encrypt(plaintext.encode())

    # 存储加密数据
    conn = sqlite3.connect("my_secure2.db")
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS secure (id INTEGER, data BLOB)")
    c.execute("INSERT INTO secure (id, data) VALUES (?, ?)", (1, encrypted))
    conn.commit()

    c.execute("SELECT data FROM secure WHERE id = 1")
    encrypted_data = c.fetchone()[0]
    decrypted = cipher.decrypt(encrypted_data).decode()
    print("Decrypted:", decrypted)
