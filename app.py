"""
Monitor Belalcázar Cloud 24/7
Servicio para Render / Servidores en la Nube
"""

import os
import sys
import time
import json
import urllib.parse
import datetime
import threading
import requests
from flask import Flask, jsonify

app = Flask(__name__)

NIT = os.environ.get("NIT", "")
PASSWORD = os.environ.get("PASSWORD", "")
WHATSAPP_PHONE = os.environ.get("WHATSAPP_PHONE", "")
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "")
INTERVALO_MINUTOS = int(os.environ.get("INTERVALO_MINUTOS", "30"))

API_BASE = "https://proveedor.supermercadobelalcazar.com/api"
VISTOS_FILE = "vistos.json"

# Base inicial con los 30 comprobantes históricos de 2026 ya vistos
VISTOS_INICIALES = [
  "abastecemos_001-CE-341747", "abastecemos_001-CE-345103", "abastecemos_001-CE-343868",
  "abastecemos_001-CE-345995", "abastecemos_001-CE-349387", "abastecemos_001-CE-348696",
  "abastecemos_001-CE-351852", "abastecemos_001-CE-350980", "abastecemos_001-CE-350829",
  "abastecemos_001-CE-354138", "abastecemos_001-CE-353861", "abastecemos_001-CE-353611",
  "abastecemos_001-CE-353078", "abastecemos_001-CE-356772", "abastecemos_001-CE-356691",
  "abastecemos_001-CE-356172", "abastecemos_001-CE-355753", "abastecemos_001-CE-355604",
  "abastecemos_001-CE-359176", "abastecemos_001-CE-358941", "abastecemos_001-CE-358778",
  "abastecemos_001-CE-358019", "abastecemos_001-CE-357865", "abastecemos_001-CE-357776",
  "abastecemos_001-CE-361750", "abastecemos_001-CE-361693", "abastecemos_001-CE-361484",
  "abastecemos_001-CE-361306", "abastecemos_001-CE-360621", "abastecemos_001-CE-360124"
]

def cargar_vistos():
    if os.path.exists(VISTOS_FILE):
        try:
            with open(VISTOS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set(VISTOS_INICIALES)

def guardar_vistos(vistos):
    try:
        with open(VISTOS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(vistos), f, indent=2)
    except Exception as e:
        print(f"[!] Error guardando vistos: {e}")

def enviar_alerta_whatsapp(mensaje: str):
    clean_phone = WHATSAPP_PHONE.replace("+", "").replace(" ", "").strip()
    encoded_text = urllib.parse.quote(mensaje)
    url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_text}&apikey={CALLMEBOT_APIKEY}"
    try:
        resp = requests.get(url, timeout=20)
        if resp.status_code == 200:
            print(f"[OK] Alerta enviada exitosamente a WhatsApp ({clean_phone})")
            return True
        else:
            print(f"[!] Error en CallMeBot: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"[!] Fallo enviando WhatsApp: {e}")
        return False

def login_belalcazar():
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    payload = {"nit": NIT, "password": PASSWORD}
    try:
        resp = requests.post(f"{API_BASE}/login.php", json=payload, headers=headers, timeout=20)
        data = resp.json()
        if resp.status_code == 200 and data.get("success"):
            return data.get("token")
        return None
    except Exception as e:
        print(f"[!] Error conectando a Belalcazar login: {e}")
        return None

def revisar_comprobantes():
    ahora = datetime.datetime.now()
    print(f"\n[{ahora.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando revisión 24/7 en la nube...")
    
    token = login_belalcazar()
    if not token:
        print("[!] No se pudo iniciar sesión en Belalcazar.")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0"
    }

    vistos = cargar_vistos()
    empresas = [("abastecemos", "Abastecemos de Occidente S.A.S"), ("tobar", "Tobar Sanchez Vallejo S.A")]
    
    # Revisamos mes actual y el mes anterior
    mes_actual = ahora.month
    anio_actual = ahora.year
    meses_a_consultar = [(anio_actual, str(mes_actual).zfill(2))]
    if mes_actual == 1:
        meses_a_consultar.append((anio_actual - 1, "12"))
    else:
        meses_a_consultar.append((anio_actual, str(mes_actual - 1).zfill(2)))

    nuevos = []

    for emp_code, emp_nombre in empresas:
        for anio, mes in meses_a_consultar:
            payload = {"empresa": emp_code, "anio": str(anio), "mes": str(mes)}
            try:
                resp = requests.post(f"{API_BASE}/comprobantes/get_comprobantes.php", json=payload, headers=headers, timeout=20)
                if resp.status_code == 200:
                    data = resp.json()
                    comps = data.get("comprobantes", [])
                    for c in comps:
                        nro = str(c.get("numero_completo") or c.get("numero"))
                        clave_unica = f"{emp_code}_{nro}"
                        if clave_unica not in vistos:
                            c["clave_unica"] = clave_unica
                            c["empresa_nombre"] = emp_nombre
                            nuevos.append(c)
            except Exception as e:
                print(f"[!] Error consultando {emp_code} {anio}-{mes}: {e}")
            time.sleep(0.5)

    if not nuevos:
        print("[i] Ningún comprobante nuevo detectado.")
        return

    print(f"[+] ¡SE DETECTARON {len(nuevos)} NUEVO(S) COMPROBANTE(S)!")
    for c in nuevos:
        nro = c.get("numero_completo") or c.get("numero")
        val = float(c.get("valor", 0) or 0)
        emp = c.get("empresa_nombre")
        fec = c.get("fecha")
        con = c.get("concepto", "Cancelación de facturas")
        
        msg = (
            f"🔔 ¡NUEVO COMPROBANTE DE BELALCÁZAR!\n\n"
            f"📄 Nro: {nro}\n"
            f"🏢 Empresa: {emp}\n"
            f"📅 Fecha: {fec}\n"
            f"💰 Valor: ${val:,.0f} COP\n"
            f"📝 Concepto: {con}\n\n"
            f"☁️ Notificado automáticamente desde el servidor en la nube."
        )
        enviar_alerta_whatsapp(msg)
        vistos.add(c["clave_unica"])
        time.sleep(2)

    guardar_vistos(vistos)

def ciclo_monitoreo():
    print("[*] Hilo vigilante en segundo plano iniciado (24/7).")
    # Espera inicial de 5 segundos antes de arrancar
    time.sleep(5)
    while True:
        try:
            revisar_comprobantes()
        except Exception as e:
            print(f"[!] Error inesperado en ciclo: {e}")
        time.sleep(INTERVALO_MINUTOS * 60)

# Endpoints de Flask para Render (Web Service gratuito)
@app.route("/")
def home():
    return jsonify({
        "servicio": "Monitor Belalcázar 24/7",
        "estado": "ACTIVO",
        "entidad": "FUNDACION UNA MANO AMIGA A TIEMPO",
        "nit": NIT,
        "whatsapp_alertas": WHATSAPP_PHONE,
        "frecuencia_minutos": INTERVALO_MINUTOS
    })

@app.route("/check-now")
def check_now():
    """Permite forzar una revisión inmediata desde el navegador"""
    revisar_comprobantes()
    return jsonify({"status": "Revisión ejecutada exitosamente"})

# Iniciar hilo vigilante
t = threading.Thread(target=ciclo_monitoreo, daemon=True)
t.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
