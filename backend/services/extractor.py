import re
import pdfplumber
import io

class UERJExtractor:
    
    # Padrão para pegar código, nome e parar antes dos números (créditos/horas)
    RID_LINE_PATTERN = r'([A-Z]{3}\d{2}-\d{5})\s+(.*?)(?=\s+\d+\s+\d+)'
    
    # Padrão histórico: Código + Nome + (Lookahead para números de carga horária)
    HIST_LINE_PATTERN = r'([A-Z]{3}\d{2}-\d{5})\s+(.*?)(?=\s+\d+\s+\d+)'
    
    SEMESTER_PATTERN = r'(\d{4}/\d)'

    @staticmethod
    def parse_rid(file_bytes: bytes) -> dict:
        """
        Lê APENAS 'Inscrição ACEITA' e ignora o resto.
        """
        full_text = ""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text(layout=True) or ""
        except Exception:
            return {}

        # 1. RECORTAR O TEXTO (Filtro de Aceitas)
        # Só olhamos o que está depois de "Inscrição ACEITA"
        if "Inscrição ACEITA" in full_text:
            full_text = full_text.split("Inscrição ACEITA")[-1]
        
        # Se tiver "Inscrição NÃO ACEITA", cortamos tudo que vem depois
        if "Inscrição NÃO ACEITA" in full_text:
            full_text = full_text.split("Inscrição NÃO ACEITA")[0]

        # Tenta achar o semestre no cabeçalho (ou usa "Atual" se não achar)
        # Como cortamos o texto, o semestre pode ter ficado pra trás, 
        # mas geralmente o RID repete ou o sistema assume o atual.
        # Para garantir, vou usar "Atual" se não achar no fragmento, 
        # mas idealmente o semestre é passado por fora ou pego antes do corte.
        semestre_atual = "Atual" 
        # (Opcional: Se quiser pegar o semestre do topo, faça a busca ANTES do split)

        disciplinas = []
        lines = full_text.split('\n')
        
        current_disc = None
        capturing_horario = False
        dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sab"]

        for line in lines:
            line = line.strip()
            
            # Regex de captura
            match = re.search(UERJExtractor.RID_LINE_PATTERN, line)
            
            if match:
                if current_disc: disciplinas.append(current_disc)
                
                codigo = match.group(1)
                nome_limpo = match.group(2).strip()
                
                current_disc = {
                    "codigo": codigo,
                    "nome": nome_limpo,
                    "horario": [],
                    "status": "Cursando",
                    "nota": None
                }
                capturing_horario = True
                continue

            if capturing_horario and current_disc:
                if any(line.startswith(d) for d in dias):
                    current_disc["horario"].append(line)
                
                if "Ramificações" in line or "Total" in line:
                    capturing_horario = False

        if current_disc: disciplinas.append(current_disc)
        
        # Retorna com a chave genérica ou você pode injetar o semestre correto na rota
        return {semestre_atual: disciplinas}

    @staticmethod
    def parse_historico(file_bytes: bytes) -> dict:
        """
        Lê histórico, corrige bug de 'um a menos' e ignora canceladas.
        """
        full_text = ""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    full_text += page.extract_text(layout=True) or ""
        except Exception:
            return {}

        historico = {}
        current_sem = None
        lines = full_text.split('\n')

        for line in lines:
            line = line.strip()

            # 1. Detecta Semestre
            sem_match = re.search(UERJExtractor.SEMESTER_PATTERN, line)
            if sem_match:
                current_sem = sem_match.group(1).replace('/', '.')
                if current_sem not in historico: historico[current_sem] = []
                # RETIREI O 'continue' AQUI! 
                # Isso corrige o bug de pular a disciplina se ela estiver na mesma linha do ano.

            # 2. Detecta Disciplina
            if current_sem:
                # Verifica se é Cancelado ANTES de tentar processar tudo
                if "Cancelado" in line:
                    continue # Pula essa linha imediatamente

                match = re.search(UERJExtractor.HIST_LINE_PATTERN, line)
                
                if match:
                    codigo = match.group(1)
                    nome_limpo = match.group(2).strip()
                    
                    # Pega Nota (Procura float no final da linha)
                    nota = None
                    # Regex busca numeros como 8,50 ou 10,00
                    numeros = re.findall(r'(\d{1,2}[.,]\d{1,2})', line)
                    if numeros:
                        try:
                            # Pega o último número da linha, que costuma ser a nota
                            nota = float(numeros[-1].replace(',', '.'))
                        except:
                            pass
                    
                    status = "Cursado"
                    if "Aprov" in line: status = "Aprovado"
                    elif "Reprov" in line: status = "Reprovado"
                    
                    # (Se fosse Cancelado, já teria caído no if acima)

                    disc = {
                        "codigo": codigo,
                        "nome": nome_limpo,
                        "nota": nota,
                        "status": status,
                        "horario": []
                    }
                    historico[current_sem].append(disc)

        return historico