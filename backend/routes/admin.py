from fastapi import APIRouter, Depends, HTTPException, Body, Query
from database import db
from security import get_current_admin
from models import User
from bson import ObjectId
from pydantic import BaseModel

router = APIRouter()

# --- MODELO DE INPUT ---
class SemestreInput(BaseModel):
    novo_semestre: str

# ==========================================
# 1. ESTATÍSTICAS
# ==========================================
@router.get("/stats")
async def get_stats(admin: User = Depends(get_current_admin)):
    total_users = await db.get_collection("users").count_documents({})
    total_disciplines = await db.get_collection("disciplines").count_documents({})
    total_warnings = await db.get_collection("warnings").count_documents({})
    
    return {
        "users": total_users,
        "disciplines": total_disciplines,
        "warnings": total_warnings
    }

# ==========================================
# 2. LISTAR USUÁRIOS
# ==========================================
@router.get("/users")
async def list_users(limit: int = 20, admin: User = Depends(get_current_admin)):
    users = await db.get_collection("users").find().sort("_id", -1).limit(limit).to_list(limit)
    result = []
    for u in users:
        u["id"] = str(u.pop("_id"))
        u.pop("senha_hash", None)
        result.append(u)
    return result

# ==========================================
# 3. DELETAR USUÁRIO (COM CASCADE DELETE)
# ==========================================
@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: User = Depends(get_current_admin)):
    """
    Remove o usuário e o retira de todas as listas de presença (turmas).
    """
    if str(admin.id) == user_id:
        raise HTTPException(400, "Você não pode deletar a si mesmo.")
    
    # Valida ID
    if not ObjectId.is_valid(user_id):
        raise HTTPException(400, "ID inválido.")
    
    oid = ObjectId(user_id)
    
    # 1. Remove da coleção de usuários
    res = await db.get_collection("users").delete_one({"_id": oid})
    
    if res.deleted_count == 0:
        raise HTTPException(404, "Usuário não encontrado")

    # 2. CORREÇÃO: Remove o ID desse usuário do array 'membros' em TODAS as disciplinas
    # $pull: remove todas as instâncias de um valor em um array
    await db.get_collection("disciplines").update_many(
        {"membros": oid}, 
        {"$pull": {"membros": oid}}
    )

    # 3. Opcional: Remover avisos postados por ele?
    # await db.get_collection("warnings").delete_many({"autor_id": user_id})

    return {"message": "Usuário deletado e removido das turmas."}

# ==========================================
# 4. DELETAR AVISO
# ==========================================
@router.delete("/warnings/{aviso_id}")
async def delete_warning_admin(aviso_id: str, admin: User = Depends(get_current_admin)):
    if not ObjectId.is_valid(aviso_id):
        raise HTTPException(400, "ID inválido.")
        
    res = await db.get_collection("warnings").delete_one({"_id": ObjectId(aviso_id)})
    if res.deleted_count == 0:
        raise HTTPException(404, "Aviso não encontrado")
    return {"message": "Aviso removido pelo admin"}

# ==========================================
# 5. ATUALIZAR PERÍODO (COM MIGRAÇÃO DE USERS E DISCIPLINES)
# ==========================================
@router.patch("/update-period")
async def update_period_only(
    payload: SemestreInput, 
    admin: User = Depends(get_current_admin)
):
    """
    1. Salva o semestre OFICIAL na coleção 'system_config' (FALTAVA ISSO).
    2. Atualiza usuários e disciplinas (migração).
    """
    novo_semestre = payload.novo_semestre.strip()
    if not novo_semestre:
        raise HTTPException(400, "O semestre não pode ser vazio.")

    # --- CORREÇÃO: Salvar na Configuração Global ---
    config_col = db.get_collection("system_config")
    await config_col.update_one(
        {"key": "semestre_ativo"},
        {"$set": {"valor": novo_semestre}},
        upsert=True # Cria se não existir
    )
    # ------------------------------------------------

    users_col = db.get_collection("users")
    disc_col = db.get_collection("disciplines")

    users_col = db.get_collection("users")
    disc_col = db.get_collection("disciplines")
    
    all_users = await users_col.find({}).to_list(None)
    count_migrados = 0
    
    # Set para guardar quais semestres antigos encontramos (ex: "Atual", "2024.2")
    # Para depois atualizar a coleção de disciplinas globais
    semestres_antigos_encontrados = set()

    # --- PARTE A: Atualiza Usuários ---
    for user in all_users:
        user_id = user["_id"]
        periodo_antigo = user.get("periodo_atual")
        disc_atuais = user.get("disciplinas_atuais", {})

        if periodo_antigo:
            # Se for diferente, marca para atualização global
            if periodo_antigo != novo_semestre:
                semestres_antigos_encontrados.add(periodo_antigo)

            # Migração da chave do dicionário do usuário
            if periodo_antigo in disc_atuais:
                dados_backup = disc_atuais[periodo_antigo]
                disc_atuais[novo_semestre] = dados_backup
                del disc_atuais[periodo_antigo] # Remove chave velha
                
                await users_col.update_one(
                    {"_id": user_id},
                    {
                        "$set": {
                            "periodo_atual": novo_semestre,
                            "disciplinas_atuais": disc_atuais
                        }
                    }
                )
                count_migrados += 1
            else:
                # Só atualiza o rótulo se não tiver dados na chave antiga
                await users_col.update_one(
                    {"_id": user_id},
                    {"$set": {"periodo_atual": novo_semestre}}
                )
        else:
            # Usuário novo sem período
            await users_col.update_one(
                {"_id": user_id},
                {"$set": {"periodo_atual": novo_semestre}}
            )

    # --- PARTE B: Atualiza Coleção Global 'disciplines' ---
    # Se encontramos usuários que estavam em "Atual", precisamos mudar 
    # as turmas globais de "Atual" para "2025.1" também.
    count_disciplinas_upd = 0
    if semestres_antigos_encontrados:
        # Atualiza todas as disciplinas que tenham o semestre antigo
        res_disc = await disc_col.update_many(
            {"semestre": {"$in": list(semestres_antigos_encontrados)}},
            {"$set": {"semestre": novo_semestre}}
        )
        count_disciplinas_upd = res_disc.modified_count

    return {
        "message": f"Semestre atualizado para '{novo_semestre}'.",
        "details": f"{count_migrados} perfis migrados.",
        "global_update": f"{count_disciplinas_upd} turmas globais atualizadas."
    }

# ==========================================
# 6. ZERAR DISCIPLINAS
# ==========================================
@router.delete("/wipe-disciplines")
async def wipe_disciplines_only(
    hard_delete: bool = Query(True, description="Se True, apaga as turmas do banco. Se False, apenas remove os alunos."),
    admin: User = Depends(get_current_admin)
):
    """
    Limpa os dados de disciplinas.
    1. Remove as disciplinas 'Em Curso' dos perfis dos alunos (Sempre).
    2. Se hard_delete=True: APAGA todas as disciplinas globais do banco.
    3. Se hard_delete=False: Apenas remove os alunos das turmas (mantém as turmas vazias).
    """
    users_col = db.get_collection("users")
    disc_col = db.get_collection("disciplines")

    # 1. Limpa referência nos usuários (Isso sempre acontece)
    res_users = await users_col.update_many(
        {}, 
        {"$set": {"disciplinas_atuais": {}}}
    )
    
    msg_disciplinas = ""

    # 2. Decide o que fazer com a coleção global
    if hard_delete:
        # --- MODO DESTRUTIVO: Apaga os documentos da coleção ---
        res_disc = await disc_col.delete_many({})
        msg_disciplinas = f"{res_disc.deleted_count} turmas globais foram APAGADAS do sistema."
    else:
        # --- MODO SUAVE: Apenas esvazia a lista de chamada ---
        res_disc = await disc_col.update_many(
            {},
            {"$set": {"membros": []}}
        )
        msg_disciplinas = f"{res_disc.modified_count} turmas foram esvaziadas (alunos removidos)."

    return {
        "message": "Limpeza concluída com sucesso.",
        "users_affected": f"{res_users.modified_count} alunos resetados.",
        "global_action": msg_disciplinas
    }