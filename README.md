# 🎓 UERJHUB

O **UERJHUB** é uma plataforma colaborativa para alunos da UERJ. O sistema automatiza o cadastro de disciplinas através da leitura de PDFs (Disciplinas em Curso e Histórico), gerencia turmas virtuais, repositórios de materiais e avaliações de professores.

## 🚀 Tecnologias

* **Linguagem:** Python 3.10+
* **Framework:** FastAPI
* **Banco de Dados:** MongoDB
* **Infraestrutura:** Docker & Docker Compose
---

## 📋 Pré-requisitos

Para rodar este projeto, você precisa ter instalado na sua máquina:

1.  **Git** (Para clonar o repositório)
2.  **Docker** e **Docker Compose** (Recomendado)

> **Nota para usuários Linux:** Certifique-se de ter seguido os passos pós-instalação do Docker para rodar comandos sem `sudo`.

---

## 🐳 Como rodar com Docker 
Esta é a forma mais fácil, pois configura o Python e o Banco de Dados automaticamente em containers isolados.

1.  **Clone o repositório (ou vá para a pasta do projeto):**
    ```bash
    cd UERJHUB
    ```

2.  **Suba os containers:**
    Este comando vai baixar as imagens, instalar as dependências e iniciar o servidor.
    ```bash
    docker compose up -d --build
    ```
    *O flag `-d` deixa o terminal livre. O `--build` garante que qualquer alteração nova seja aplicada.*

3.  **Verifique se está rodando:**
    ```bash
    docker compose logs -f api
    ```
    *Se aparecer "Application startup complete", está tudo pronto!*

4.  **Acesse a Documentação (Swagger):**
    Abra seu navegador em: **[http://localhost:8000/docs](http://localhost:8000/docs)**

---

## 🛠️ Como rodar Manualmente 

Caso prefira rodar localmente para desenvolvimento rápido:

1.  **Tenha o MongoDB rodando:**
    Certifique-se de que o MongoDB está instalado e rodando na porta `27017`.

2.  **Crie um ambiente virtual:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # Linux/Mac
    # .venv\Scripts\activate   # Windows
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Rode o servidor:**
    Entre na pasta `backend` e inicie o uvicorn:
    ```bash
    cd backend
    uvicorn main:app --reload
    ```

---

## ⚛️ Como Rodar o Frontend

1.  **Rode o servidor:**
    Entre na pasta `frontend` e use o comando:
    ```bash
    cd frantend
    python3 -m http.server 3000
    ```
2. **Acesse em:** 

Abra seu navegador em: **[http://localhost:3000/login](http://localhost:3000/login)**

---
