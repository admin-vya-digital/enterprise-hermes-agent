"""
Outreach Gap Analysis — reference implementation

Pattern: verify campaign coverage by matching an eligibility rule against outreach logs.
Handles messy API exports (line-number prefixes, string numerics) and produces a
per-segment gap report.

How to use:
1. Place this script in the project directory near your data files.
2. Update the path constants to point to your files.
3. Adjust the `alvos` set and field names to match your schema.
4. Run: python outreach-gap-pattern.py
"""

import json
import csv
import sys
from pathlib import Path
from collections import defaultdict

# ─── CONFIGURE PATHS ─────────────────────────────────────────────────────
BASE_API_PATH = Path('/home/praxislatina/Área de trabalho/Pasta sem título/base_api.txt')
ACIONAMENTO_PF_PATH = Path('/home/praxislatina/Área de trabalho/Pasta sem título/acionamentoPF.csv')
ACIONAMENTO_PJ_PATH = Path('/home/praxislatina/Área de trabalho/Pasta sem título/acionamentoPJ.csv')

# ─── BUSINESS RULE ────────────────────────────────────────────────────
ALVOS = {5, 15, 20, 30, 40, 50, 60}

# ─── HELPER: EXTRACT JSON FROM PREFIXED FILE ───────────────────────────
def extract_json_from_prefixed_lines(path: Path) -> dict | list:
    """Handle files with line-number prefixes like "123| {\"field\":...}"""
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        raw_lines = f.readlines()

    # Remove "N|" prefix from each line
    stripped = []
    for line in raw_lines:
        if '|' in line:
            _, rest = line.split('|', 1)
            stripped.append(rest)
        else:
            stripped.append(line)

    # Join and find JSON boundaries
    joined = ''.join(stripped)
    start = joined.find('{')
    if start == -1:
        start = joined.find('[')
    end = joined.rfind('}')
    if end == -1:
        end = joined.rfind(']')
    if start == -1 or end == -1:
        raise ValueError('Could not locate JSON boundaries in file')

    json_str = joined[start:end+1]
    return json.loads(json_str, strict=False)

# ─── MAIN LOGIC ────────────────────────────────────────────────────────

def main():
    # Load source data
    data = extract_json_from_prefixed_lines(BASE_API_PATH)
    if isinstance(data, dict) and 'Data' in data:
        records = data['Data']
    else:
        records = data

    print(f"Total records in source: {len(records)}", file=sys.stderr)

    # Build eligibility sets
    pf_alvo, pj_alvo = [], []
    for r in records:
        # Coerce dias
        try:
            dias = int(r.get('DIAS_DE_ATRASO', 0))
        except (ValueError, TypeError):
            dias = 0

        tipo = r.get('TIPO_PESSOA', '').strip().upper()
        cpf_cnpj = r.get('CPF_CNPJ')
        nome = r.get('NOME_TITULAR', '')

        if not cpf_cnpj or dias not in ALVOS:
            continue

        entry = {'cpf_cnpj': cpf_cnpj, 'nome': nome, 'dias': dias}
        if tipo == 'FISICA':
            pf_alvo.append(entry)
        elif tipo == 'JURIDICA':
            pj_alvo.append(entry)

    # Load outreach logs
    def load_keys(path: Path, delimiter=';') -> set[str]:
        keys = set()
        if not path.exists():
            return keys
        with open(path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                cnpj = row.get('CPFCNPJ')
                if cnpj:
                    keys.add(cnpj)
        return keys

    pf_acionados = load_keys(ACIONAMENTO_PF_PATH)
    pj_acionados = load_keys(ACIONAMENTO_PJ_PATH)

    # Compute gaps
    pf_sim = [r for r in pf_alvo if r['cpf_cnpj'] in pf_acionados]
    pf_nao = [r for r in pf_alvo if r['cpf_cnpj'] not in pf_acionados]

    pj_sim = [r for r in pj_alvo if r['cpf_cnpj'] in pj_acionados]
    pj_nao = [r for r in pj_alvo if r['cpf_cnpj'] not in pj_acionados]

    # Reporting helpers
    def group_by_dias(records):
        out = defaultdict(list)
        for r in records:
            out[r['dias']].append(r)
        return out

    # ─── REPORT ──────────────────────────────────────────────────────
    print('\n=== OUTREACH GAP REPORT ===')
    print('\n--- PF ---')
    print(f'Elegíveis: {len(pf_alvo)}')
    print(f'Acionados: {len(pf_sim)}')
    print(f'Pendentes: {len(pf_nao)}')

    pf_by_dias = group_by_dias(pf_nao)
    if pf_nao:
        print('Detalhamento pendentes por dias:')
        for dias in sorted(pf_by_dias.keys()):
            print(f'  {dias} dias: {len(pf_by_dias[dias])}')
        print('Amostra (até 10):')
        for r in pf_nao[:10]:
            print(f"  {r['cpf_cnpj']} | {r['nome'][:45]} | {r['dias']}")
    else:
        print('  ✅ Todos acionados.')

    print('\n--- PJ ---')
    print(f'Elegíveis: {len(pj_alvo)}')
    print(f'Acionados: {len(pj_sim)}')
    print(f'Pendentes: {len(pj_nao)}')

    pj_by_dias = group_by_dias(pj_nao)
    if pj_nao:
        print('Detalhamento pendentes por dias:')
        for dias in sorted(pj_by_dias.keys()):
            print(f'  {dias} dias: {len(pj_by_dias[dias])}')
        print('Amostra (até 10):')
        for r in pj_nao[:10]:
            print(f"  {r['cpf_cnpj']} | {r['nome'][:45]} | {r['dias']}")
    else:
        print('  ✅ Todos acionados.')


if __name__ == '__main__':
    main()