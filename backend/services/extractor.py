import re
import pdfplumber
import io

class UERJExtractor:
    
    # REGEX GERAIS
    SEMESTER_PATTERN = r'(\d{4}/\d)'
    CODE_PATTERN_START = r'([A-Z]{3}\d{2}-\d{5})\s+(.*)' 
    CODE_PATTERN = r'([A-Z]{3}\d{2}-\d{5})'

    @staticmethod
    def parse_rid(file_bytes: bytes) -> dict:
        print(f"--- LENDO TURMAS EM CURSO ---")
        
        disciplinas_map = {} 
        semestre = "Atual"

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                
                full_text_all = ""
                
                for page in pdf.pages:
                    full_text_all += page.extract_text(layout=True) or ""
                    words = page.extract_words(keep_blank_chars=False)
                    
                    # 1. Identificar a coluna "TURMA" (Cabeçalho)
                    turma_header = next((w for w in words if "TURMA" in w['text'].upper()), None)
                    
                    # Define a zona onde esperamos encontrar os números das turmas (Eixo X)
                    turma_zone_min = 0
                    turma_zone_max = 0
                    
                    if turma_header:
                        mid_x = (turma_header['x0'] + turma_header['x1']) / 2
                        turma_zone_min = mid_x - 50 # Zona de busca
                        turma_zone_max = mid_x + 50

                    # 2. Varrer palavras procurando códigos das matérias (FEN...)
                    for w in words:
                        if re.match(UERJExtractor.CODE_PATTERN, w['text']):
                            codigo = w['text']
                            row_y = (w['top'] + w['bottom']) / 2 # Linha Y da matéria
                            
                            # --- A. DETECTAR A TURMA (EIXO X/Y) ---
                            turma_detectada = "1"
                            turma_word_obj = None # Vamos guardar o objeto da palavra "1" ou "10"
                            
                            if turma_header:
                                for candidate in words:
                                    cand_y = (candidate['top'] + candidate['bottom']) / 2
                                    cand_mid_x = (candidate['x0'] + candidate['x1']) / 2
                                    
                                    # Verifica se está na mesma linha e dentro da zona da coluna Turma
                                    if abs(cand_y - row_y) < 5 and \
                                       turma_zone_min <= cand_mid_x <= turma_zone_max:
                                        if candidate['text'].isdigit():
                                            turma_detectada = candidate['text']
                                            turma_word_obj = candidate
                                            break
                            
                            # --- B. DEFINIR O LIMITE DO NOME ---
                            # Se achamos o número da turma, o nome pode ir até encostar nele.
                            # Se não achamos, usamos o início do cabeçalho "TURMA" como limite.
                            if turma_word_obj:
                                # O limite é o X0 (início) do número da turma - 5px de margem
                                limit_x = turma_word_obj['x0'] - 2 
                            elif turma_header:
                                limit_x = turma_header['x0'] - 5
                            else:
                                limit_x = 9999 # Fallback (não deve acontecer)

                            # --- C. MONTAR O NOME ---
                            if codigo not in disciplinas_map:
                                nome_parts = []
                                for nm_word in words:
                                    nm_y = (nm_word['top'] + nm_word['bottom']) / 2
                                    
                                    # Mesma linha da matéria?
                                    if abs(nm_y - row_y) < 5:
                                        # É o próprio código? Ignora.
                                        if nm_word['text'] == codigo: continue
                                        
                                        # Está À ESQUERDA do limite definido?
                                        if nm_word['x1'] <= limit_x:
                                            nome_parts.append(nm_word['text'])
                                
                                # Junta tudo
                                nome_bruto = " ".join(nome_parts)
                                
                                # --- LIMPEZA ---
                                # 1. Remove numeração de lista no início (ex: "1. ", "2 ", "10.")
                                nome_limpo = re.sub(r'^\s*\d+[\.\s]+', '', nome_bruto)
                                
                                # 2. Remove pontuação solta no início
                                nome_limpo = re.sub(r'^[.\-\s]+', '', nome_limpo).strip()

                                disciplinas_map[codigo] = {
                                    "codigo": codigo,
                                    "nome": nome_limpo,
                                    "turma": turma_detectada, 
                                    "horario": [],
                                    "status": "Cursando",
                                    "nota": None,
                                    "disciplina_id": None
                                }

                # Pega o semestre
                match_sem = re.search(UERJExtractor.SEMESTER_PATTERN, full_text_all)
                if match_sem: semestre = match_sem.group(1).replace('/', '.')

                # ==========================================================
                # PASSO 2: EXTRAÇÃO DE HORÁRIOS (MANTIDO)
                # ==========================================================
                for page in pdf.pages:
                    words = page.extract_words(keep_blank_chars=False)
                    dias_labels = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
                    dias_short = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]
                    found_headers = []
                    for w in words:
                        if w['text'] in dias_labels:
                            idx = dias_labels.index(w['text'])
                            found_headers.append({'label': dias_short[idx], 'data': w})
                    found_headers.sort(key=lambda h: h['data']['x0'])
                    
                    col_ranges = []
                    for i in range(len(found_headers)):
                        curr = found_headers[i]
                        start_x = curr['data']['x0'] - 5 
                        end_x = (curr['data']['x1'] + found_headers[i+1]['data']['x0']) / 2 if i < len(found_headers)-1 else 9999
                        col_ranges.append({'dia': curr['label'], 'min_x': start_x, 'max_x': end_x})

                    time_rows = []
                    time_pattern = re.compile(r'^[MTN]\d$') 
                    for i, w in enumerate(words):
                        if time_pattern.match(w['text']):
                            look_ahead = words[i+1:i+8] 
                            full_line_str = "".join([x['text'] for x in look_ahead])
                            match_hour = re.search(r'(\d{2}:\d{2}.*?\d{2}:\d{2})', full_line_str)
                            if match_hour:
                                clean_hour = match_hour.group(1).replace(')', '').strip().replace('-', ' - ')
                                time_rows.append({'label': clean_hour, 'mid_y': (w['top'] + w['bottom']) / 2})

                    for w in words:
                        if re.match(UERJExtractor.CODE_PATTERN, w['text']):
                            codigo = w['text']
                            w_mid_x = (w['x0'] + w['x1']) / 2
                            w_mid_y = (w['top'] + w['bottom']) / 2
                            dia = next((c['dia'] for c in col_ranges if c['min_x'] <= w_mid_x <= c['max_x']), None)
                            hora = next((r['label'] for r in time_rows if abs(w_mid_y - r['mid_y']) < 10), None)
                            if dia and hora and codigo in disciplinas_map:
                                final_str = f"{dia} {hora}"
                                if final_str not in disciplinas_map[codigo]["horario"]:
                                    disciplinas_map[codigo]["horario"].append(final_str)

        except Exception as e:
            print(f" Erro PDF DISCIPLINAS EM CURSO: {e}")
            return {}

        dias_ordem = {"Seg": 0, "Ter": 1, "Qua": 2, "Qui": 3, "Sex": 4, "Sab": 5}
        for disc in disciplinas_map.values():
            disc["horario"].sort(key=lambda x: (dias_ordem.get(x.split()[0], 9), x.split()[1]))

        return {semestre: list(disciplinas_map.values())}

    @staticmethod
    def parse_historico(file_bytes: bytes) -> dict:
        print("--- INICIANDO EXTRAÇÃO HISTÓRICO ---")
        full_text = ""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text(layout=True) or ""
        except: return {}

        historico = {}
        codigos_vistos_no_semestre = set() 
        current_sem = None
        lines = full_text.split('\n')

        for line in lines:
            line = line.strip()
            if not line: continue

            # 1. Semestre
            sem_match = re.search(UERJExtractor.SEMESTER_PATTERN, line)
            if sem_match:
                current_sem = sem_match.group(1).replace('/', '.')
                if current_sem not in historico: 
                    historico[current_sem] = []
                    codigos_vistos_no_semestre = set()
                    print(f"📅 Semestre: {current_sem}")

            # 2. Ignora Cancelado
            if "Cancelado" in line: continue

            # 3. Disciplina
            if current_sem:
                match = re.search(UERJExtractor.CODE_PATTERN_START, line)
                if match:
                    codigo = match.group(1)
                    
                    if codigo in codigos_vistos_no_semestre:
                        continue
                    codigos_vistos_no_semestre.add(codigo)

                    resto = match.group(2)
                    split_nome = re.split(r'(\d)', resto, maxsplit=1)
                    nome_limpo = split_nome[0].strip()
                    
                    nota = None
                    nums = re.findall(r'(\d{1,2}[.,]\d{1,2})', line)
                    if nums:
                        try: nota = float(nums[-1].replace(',', '.'))
                        except: pass

                    status = "Cursado"
                    if "Aprov" in line: status = "Aprovado"
                    elif "Reprov" in line: status = "Reprovado"

                    historico[current_sem].append({
                        "codigo": codigo,
                        "nome": nome_limpo,
                        "nota": nota,
                        "status": status,
                        "horario": [],
                        "turma": None 
                    })

        return historico