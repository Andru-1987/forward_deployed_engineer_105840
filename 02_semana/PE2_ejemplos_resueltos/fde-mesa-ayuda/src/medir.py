"""Corre 5 consultas reales y arma la tabla de medición que pide la PE2.

    uv run python src/medir.py                       con el proveedor de config.toml
    uv run python src/medir.py --proveedor groq      con otro proveedor
    uv run python src/medir.py --todos               compara todos los que tengan clave en .env

Guarda las tablas en resultados/ para pegarlas en el PDF.
"""

import argparse

from configuracion import CONFIG, RAIZ
from motor import procesar
from proveedores import PROVEEDORES, datos_proveedor, falta_clave, proveedor_activo

CONSULTAS = [
    ("Caso típico", {"legajo": "EMP-0142",
                     "mensaje": "Olvidé mi contraseña del correo y no puedo entrar."}),
    ("Caso típico", {"legajo": "EMP-0207",
                     "mensaje": "La impresora del segundo piso imprime todo con rayas."}),
    ("Caso límite", {"legajo": "EMP-0315",
                     "mensaje": "Nadie del área de ventas tiene internet desde las 9 y "
                                "tenemos clientes esperando."}),
    ("Confusa", {"legajo": "EMP-0420",
                 "mensaje": "lo de ayer sigue igual, ya lo reinicié y nada, fijate"}),
    ("Fuera de tema", {"legajo": "EMP-0533",
                       "mensaje": "¿Saben si el viernes hay asado de fin de año?"}),
]
TITULO_DETALLE = "Tipo / prioridad o error"


def detalle(r: dict) -> str:
    """Qué mostrar de cada respuesta en la tabla."""
    return f"{r['salida']['tipo']} / {r['salida']['prioridad']}" if r["ok"] else r["etapa"]


def medir(proveedor: str) -> dict:
    """Corre las 5 consultas con un proveedor y devuelve filas y promedios."""
    filas = []
    for numero, (tipo, datos) in enumerate(CONSULTAS, start=1):
        r = procesar(datos, proveedor)
        filas.append({"n": numero, "tipo": tipo, "ok": r["ok"], "detalle": detalle(r),
                      "t_in": r["tokens_entrada"], "t_out": r["tokens_salida"],
                      "costo": r["costo_usd"], "latencia": r["latencia_ms"],
                      "intentos": r["intentos"]})
        print(f"[{proveedor}] {numero}. {tipo}: ok={r['ok']} {detalle(r)} | "
              f"{r['tokens_entrada']}/{r['tokens_salida']} tokens | "
              f"{r['costo_usd']} USD | {r['latencia_ms']} ms")
    n = len(filas)
    return {
        "proveedor": proveedor,
        "filas": filas,
        "validadas": sum(f["ok"] for f in filas),
        "t_in": sum(f["t_in"] for f in filas) / n,
        "t_out": sum(f["t_out"] for f in filas) / n,
        "costo": sum(f["costo"] for f in filas) / n,
        "latencia": sum(f["latencia"] for f in filas) / n,
    }


def tabla_detallada(m: dict) -> str:
    datos = datos_proveedor(m["proveedor"])
    lineas = [
        f"Proveedor: {m['proveedor']} · modelo: {datos['modelo']} · plan: {datos['plan']}",
        "",
        f"| # | Consulta | ¿Validó? | {TITULO_DETALLE} | Tokens (entrada / salida) "
        "| Costo USD | Latencia ms | Intentos |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for f in m["filas"]:
        lineas.append(f"| {f['n']} | {f['tipo']} | {'Sí' if f['ok'] else 'No'} | {f['detalle']} "
                      f"| {f['t_in']} / {f['t_out']} | {f['costo']:.6f} | {f['latencia']} "
                      f"| {f['intentos']} |")
    lineas.append(f"| | **Promedio** | | | {m['t_in']:.0f} / {m['t_out']:.0f} "
                  f"| {m['costo']:.6f} | {m['latencia']:.0f} | |")
    lineas.append("")
    lineas.append(f"- Consultas validadas: {m['validadas']} de {len(m['filas'])}")
    if m["validadas"] == 0:
        lineas.append("- Ninguna consulta llegó al modelo: revisá la clave en .env "
                      "y el modelo en config.toml.")
        return "\n".join(lineas)
    meta_lat = CONFIG["kpi"]["meta_latencia_ms"]
    meta_costo = CONFIG["kpi"]["meta_costo_usd"]
    lineas.append(f"- Meta de latencia (PE1): {meta_lat} ms → "
                  f"{'cumple' if m['latencia'] <= meta_lat else 'no cumple'}")
    lineas.append(f"- Meta de costo por consulta (PE1): {meta_costo} USD → "
                  f"{'cumple' if m['costo'] <= meta_costo else 'no cumple'}")
    if datos["plan"] == "gratis":
        lineas.append("- Plan gratuito: no pagás, pero el costo se calcula con la tarifa "
                      "paga para que la medición sirva para decidir.")
    return "\n".join(lineas)


def tabla_comparativa(mediciones: list[dict]) -> str:
    lineas = [
        "| Proveedor | Modelo | Plan | Validadas | Tokens promedio (entrada / salida) "
        "| Costo USD promedio | Latencia ms promedio |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in mediciones:
        datos = datos_proveedor(m["proveedor"])
        lineas.append(f"| {m['proveedor']} | {datos['modelo']} | {datos['plan']} "
                      f"| {m['validadas']} de {len(m['filas'])} "
                      f"| {m['t_in']:.0f} / {m['t_out']:.0f} | {m['costo']:.6f} "
                      f"| {m['latencia']:.0f} |")
    return "\n".join(lineas)


def guardar(nombre: str, texto: str) -> None:
    destino = RAIZ / "resultados" / nombre
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(texto + "\n", encoding="utf-8")
    print(f"\n{texto}\n\nTabla guardada en {destino.relative_to(RAIZ)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mide 5 consultas reales")
    parser.add_argument("--proveedor", choices=PROVEEDORES, help="por defecto, el de config.toml")
    parser.add_argument("--todos", action="store_true",
                        help="compara todos los proveedores que tengan clave en .env")
    args = parser.parse_args()

    if not args.todos:
        proveedor = proveedor_activo(args.proveedor)
        guardar(f"medicion_{proveedor}.md", tabla_detallada(medir(proveedor)))
        return

    con_clave = [p for p in PROVEEDORES if not falta_clave(p)]
    if not con_clave:
        print("No hay ninguna clave en .env. Completá al menos una y volvé a probar.")
        return
    mediciones = [medir(p) for p in con_clave]
    texto = "\n\n".join(tabla_detallada(m) for m in mediciones)
    guardar("comparacion.md", tabla_comparativa(mediciones) + "\n\n" + texto)


if __name__ == "__main__":
    main()
