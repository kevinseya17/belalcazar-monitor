"""
Ejecutor de revisión para GitHub Actions / Cron Jobs con generación automática de PDF
"""

import os
import sys
import time
import json
import urllib.parse
import datetime
import requests
from pdf_generator import generar_pdf_comprobante

NIT = os.environ.get("NIT", "901369891")
PASSWORD = os.environ.get("PASSWORD", "901369891")
DESTINATARIOS = [
    {"phone": "573137493049", "apikey": "5358764"},
    {"phone": "573142407755", "apikey": "3564255"}
]

API_BASE = "https://proveedor.supermercadobelalcazar.com/api"
VISTOS_FILE = "vistos.json"
PDF_DIR = "pdfs"

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
    with open(VISTOS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(vistos), f, indent=2)

def enviar_alerta_whatsapp(mensaje: str):
    encoded_text = urllib.parse.quote(mensaje)
    for dest in DESTINATARIOS:
        phone = dest["phone"].replace("+", "").replace(" ", "").strip()
        apikey = dest["apikey"]
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_text}&apikey={apikey}"
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                print(f"[OK] Alerta enviada exitosamente a WhatsApp ({phone})")
            else:
                print(f"[!] Error CallMeBot ({phone}): {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"[!] Error WhatsApp ({phone}): {e}")
        time.sleep(1.5)

def login():
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    payload = {"nit": NIT, "password": PASSWORD}
    try:
        resp = requests.post(f"{API_BASE}/login.php", json=payload, headers=headers, timeout=20)
        data = resp.json()
        if resp.status_code == 200 and data.get("success"):
            return data.get("token")
        return None
    except Exception as e:
        print(f"[!] Error login: {e}")
        return None

def main():
    ahora = datetime.datetime.now()
    print(f"[{ahora.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando revisión en GitHub Actions...")
    
    os.makedirs(PDF_DIR, exist_ok=True)
    token = login()
    if not token:
        print("[!] No se pudo iniciar sesión.")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0"
    }

    vistos = cargar_vistos()
    empresas = [("abastecemos", "Abastecemos de Occidente S.A.S"), ("tobar", "Tobar Sanchez Vallejo S.A")]
    
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
                    comps = resp.json().get("comprobantes", [])
                    for c in comps:
                        nro = str(c.get("numero_completo") or c.get("numero"))
                        clave = f"{emp_code}_{nro}"
                        if clave not in vistos:
                            c["clave_unica"] = clave
                            c["empresa_nombre"] = emp_nombre
                            c["empresa_codigo"] = emp_code
                            nuevos.append(c)
            except Exception as e:
                print(f"[!] Error {emp_code} {anio}-{mes}: {e}")
            time.sleep(0.5)

    if not nuevos:
        print("[i] No hay nuevos comprobantes en esta revisión.")
        guardar_vistos(vistos)
        return

    print(f"[+] ¡{len(nuevos)} nuevo(s) comprobante(s) detectado(s)!")
    for c in nuevos:
        nro = c.get("numero_completo") or c.get("numero")
        emp_code = c.get("empresa_codigo", "abastecemos")
        val = float(c.get("valor", 0) or 0)
        emp = c.get("empresa_nombre")
        fec = c.get("fecha")
        con = c.get("concepto", "Cancelación de facturas")
        clean_nro = str(nro).replace("/", "_").replace("\\", "_")
        pdf_path = os.path.join(PDF_DIR, f"{clean_nro}.pdf")

        # 1. Generar PDF en la nube
        try:
            det_resp = requests.post(
                f"{API_BASE}/comprobantes/generate_comprobante.php",
                json={"comprobante": nro, "empresa": emp_code},
                headers=headers,
                timeout=25
            )
            det_data = det_resp.json()
            if det_data.get("success"):
                generar_pdf_comprobante(det_data, pdf_path)
                print(f"[OK] PDF generado: {pdf_path}")
        except Exception as e_pdf:
            print(f"[!] Error generando PDF para {nro}: {e_pdf}")

        # 2. Enlace directo para abrir o descargar el PDF desde el celular
        pdf_link = f"https://github.com/kevinseya17/belalcazar-monitor/blob/main/pdfs/{clean_nro}.pdf"

        # 3. Notificación a WhatsApp
        msg = (
            f"🔔 ¡NUEVO COMPROBANTE DE BELALCÁZAR!\n\n"
            f"📄 Nro: {nro}\n"
            f"🏢 Empresa: {emp}\n"
            f"📅 Fecha: {fec}\n"
            f"💰 Valor: ${val:,.0f} COP\n"
            f"📝 Concepto: {con}\n\n"
            f"📥 Ver/Descargar PDF desde tu celular:\n{pdf_link}"
        )
        enviar_alerta_whatsapp(msg)
        vistos.add(c["clave_unica"])
        time.sleep(2)

    guardar_vistos(vistos)
    print("[OK] Revisión completada y registros actualizados.")

if __name__ == "__main__":
    main()
