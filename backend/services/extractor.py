import re
import pdfplumber
import io

class UERJExtractor:
    
    # REGEX GERAIS
    SEMESTER_PATTERN = r'(\d{4}/\d)'
    CODE_PATTERN_START = r'([A-Z]{3}\d{2}-\d{5})\s+(.*)' 

    @staticmethod
    def parse_rid(file_bytes: bytes) -> dict:
        print("--- INICIANDO EXTRAÇÃO DO RID (SEM DUPLICATAS) ---")
        full_text = ""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text(layout=True) or ""
        except Exception as e:
            print(f"❌ Erro PDF RID: {e}")
            return {}

        # 1. Filtro de Seção
        text_upper = full_text.upper()
        idx_aceita = text_upper.find("INSCRIÇÃO ACEITA")
        idx_nao_aceita = text_upper.find("INSCRIÇÃO NÃO ACEITA")

        if idx_aceita != -1:
            relevant_text = full_text[idx_aceita:]
            if idx_nao_aceita != -1 and idx_nao_aceita > idx_aceita:
                relevant_text = relevant_text[:idx_nao_aceita - idx_aceita]
        else:
            relevant_text = full_text

        sem_match = re.search(r'(\d{4}/\d)', full_text)
        semestre_atual = sem_match.group(1).replace('/', '.') if sem_match else "Atual"

        disciplinas = []
        codigos_vistos = set() # <--- O SEGREDINHO ANTI-DUPLICIDADE
        
        lines = relevant_text.split('\n')
        current_disc = None
        capturing_horario = False
        dias_semana = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]

        for line in lines:
            line = line.strip()
            if not line: continue

            match = re.search(UERJExtractor.CODE_PATTERN_START, line)
            
            if match:
                # Salva o anterior antes de começar o novo
                if current_disc: 
                    disciplinas.append(current_disc)
                
                codigo = match.group(1)
                
                # SE JÁ VIMOS ESSE CÓDIGO NESTE ARQUIVO, IGNORA (Evita duplicata)
                if codigo in codigos_vistos:
                    print(f"⚠️ Ignorando duplicata no RID: {codigo}")
                    current_disc = None # Reseta para não capturar horário de duplicata
                    capturing_horario = False
                    continue
                
                codigos_vistos.add(codigo) # Marca como visto

                resto = match.group(2)
                split_nome = re.split(r'(\d)', resto, maxsplit=1)
                nome_limpo = split_nome[0].strip()
                
                turma = "1"
                if len(split_nome) > 1:
                    numeros = re.findall(r'\b\d+\b', split_nome[1] + split_nome[2])
                    if len(numeros) >= 4:
                        turma = str(int(numeros[3]))

                current_disc = {
                    "codigo": codigo,
                    "nome": nome_limpo,
                    "turma": turma,
                    "horario": [],
                    "status": "Cursando",
                    "nota": None,
                    "disciplina_id": None
                }
                
                for d in dias_semana:
                    if d in resto:
                        idx_dia = line.find(d)
                        if idx_dia != -1: current_disc["horario"].append(line[idx_dia:])
                        break

                capturing_horario = True
                continue

            if capturing_horario and current_disc:
                if any(line.startswith(d) for d in dias_semana):
                    current_disc["horario"].append(line)
                
                if "Inscrição" in line or "Total" in line:
                    capturing_horario = False

        if current_disc: disciplinas.append(current_disc)
        return {semestre_atual: disciplinas}

    @staticmethod
    def parse_historico(file_bytes: bytes) -> dict:
        print("--- INICIANDO EXTRAÇÃO HISTÓRICO (SEM DUPLICATAS) ---")
        full_text = ""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text(layout=True) or ""
        except: return {}

        historico = {}
        codigos_vistos_no_semestre = set() # <--- NOVO
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
                    codigos_vistos_no_semestre = set() # Reseta o set a cada semestre novo
                    print(f"📅 Semestre: {current_sem}")

            # 2. Ignora Cancelado
            if "Cancelado" in line: continue

            # 3. Disciplina
            if current_sem:
                match = re.search(UERJExtractor.CODE_PATTERN_START, line)
                if match:
                    codigo = match.group(1)
                    
                    # Checagem de Duplicidade dentro do MESMO semestre
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