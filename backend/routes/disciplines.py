from fastapi import APIRouter, HTTPException, Depends, status
from database import db
from models import Discipline, User
from typing import List
from bson import ObjectId

router = APIRouter()

@router.post("/sync/{user_id}")
async def sync_student_classes(user_id: str):
    """
    1. Lê as 'disciplinas_atuais' do Aluno.
    2. Para cada disciplina:
       - Verifica se já existe uma Turma criada na coleção 'disciplines'.
       - Se NÃO existir: CRIA a turma e põe o aluno como membro.
       - Se JÁ existir: Só adiciona o aluno na lista de membros.
    3. Atualiza o ID da disciplina no perfil do aluno.
    """
    try:
        users_col = db.get_collection("users")
        disc_col = db.get_collection("disciplines")
        
        # 1. Busca o Aluno
        user = await users_col.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(404, "Usuário não encontrado")
            
        periodo_atual = user.get("periodo_atual", "2025.1")
        
        # Pega a lista do semestre atual (Dicionário)
        if periodo_atual not in user.get("disciplinas_atuais", {}):
            return {"message": "Nenhuma disciplina encontrada para o período atual."}

        lista_disciplinas = user["disciplinas_atuais"][periodo_atual]
        lista_atualizada = []

        # 2. Itera sobre as matérias do aluno
        for materia in lista_disciplinas:
            codigo = materia["codigo"]
            turma = materia.get("turma", "1")
            nome = materia["nome"]
            
            # Busca se a SALA DE AULA já existe
            filtro = {
                "codigo": codigo,
                "turma": turma,
                "semestre": periodo_atual
            }
            
            sala_existente = await disc_col.find_one(filtro)
            
            sala_id = None
            
            if sala_existente:
                # CENÁRIO A: Sala existe. Adiciona aluno se não estiver lá.
                sala_id = sala_existente["_id"]
                if ObjectId(user_id) not in sala_existente["membros"]:
                    await disc_col.update_one(
                        {"_id": sala_id},
                        {"$push": {"membros": ObjectId(user_id)}}
                    )
            else:
                # CENÁRIO B: Sala não existe. O aluno inaugura a sala.
                nova_sala = Discipline(
                    codigo=codigo,
                    nome=nome,
                    turma=turma,
                    semestre=periodo_atual,
                    membros=[ObjectId(user_id)] # Primeiro membro
                )
                result = await disc_col.insert_one(nova_sala.model_dump(by_alias=True, exclude=["id"]))
                sala_id = result.inserted_id

            # Atualiza o objeto do aluno com o ID oficial da sala
            materia["disciplina_id"] = str(sala_id)
            lista_atualizada.append(materia)

        # 3. Salva as atualizações no Aluno (para ele ter o ID da sala)
        path_update = f"disciplinas_atuais.{periodo_atual}"
        await users_col.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {path_update: lista_atualizada}}
        )

        return {"status": "Sincronizado", "total_turmas": len(lista_atualizada)}

    except Exception as e:
        print(e)
        raise HTTPException(500, f"Erro na sincronização: {str(e)}")