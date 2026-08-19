<!-- Guide autonome de construction de l'authentification, des rôles et de la visibilité du dashboard. -->

# Simulateur de parcours assuré CMU

## Étape 7/10 — Authentification, rôles et visibilité

**Tutoriel d'exécution manuelle — nouvelle étape, à la suite des étapes 1 à 6 déjà réalisées.**

Cette étape ajoute une couche d'authentification complète : une table
utilisateurs, trois rôles (administrateur, opérateur, observateur), une
protection des endpoints sensibles côté API, une page de connexion côté
dashboard, un onglet de gestion des utilisateurs réservé aux administrateurs,
et une visibilité du dashboard qui s'adapte au rôle connecté.

---

## 1. Résultat attendu

- Une nouvelle table `TB_UTILISATEURS` (migration `20260814_0004`).
- Un mot de passe **jamais stocké en clair** (hachage `bcrypt`).
- Une authentification par **jeton JWT** (`POST /auth/login`), valable 8 heures.
- Les endpoints de pilotage (`/simulation/start`, `/simulation/stop`,
  `/simulation/speed`) exigent désormais le rôle `operateur` ou
  `administrateur`.
- Les endpoints de gestion des utilisateurs (`/users`) exigent le rôle
  `administrateur`.
- Un compte administrateur initial créé via un script dédié (jamais de mot
  de passe par défaut codé en dur).
- Côté dashboard : une page de connexion, un onglet « Utilisateurs » visible
  uniquement par les administrateurs, et une interface qui masque les
  actions et les onglets non autorisés selon le rôle connecté (voir tableau
  section 11).

**Ce que cette étape ne fait pas** : pas de récupération de mot de passe par
email (hors périmètre d'une démonstration), pas d'authentification à deux
facteurs.

---

## 2. Hypothèses et choix techniques

| Choix | Pourquoi |
|---|---|
| `bcrypt` (bibliothèque directe, pas `passlib`) | `passlib` n'est plus maintenu et pose des soucis de compatibilité avec les versions récentes de `bcrypt` ; la bibliothèque `bcrypt` seule suffit largement ici. |
| JWT (`PyJWT`) plutôt que des sessions serveur | Plus simple à faire cohabiter avec Socket.IO (le token est simplement renvoyé à chaque connexion), pas d'état de session à synchroniser côté serveur. |
| Jeton valable 8 heures | Couvre une session de travail/démonstration sans avoir à se reconnecter sans arrêt ; pas de rafraîchissement automatique du jeton dans cette v1. |
| 3 rôles fixes en base (`CHECK` SQL), pas de table de rôles séparée | Le besoin est simple et fermé (3 rôles connus à l'avance) ; une table séparée serait une complexité inutile pour ce projet. |
| `UTILISATEUR_UUID` en clé primaire | Cohérent avec le reste du schéma (ex. `TB_REF_ASSURES`), plutôt qu'un entier auto-incrémenté. |
| Jeton stocké côté client dans `localStorage` | Standard pour une SPA React ; le jeton expire après 8h de toute façon, donc le risque est limité pour une démonstration. |

**Rappel de la règle Alembic :** cette étape ajoute la migration
`20260814_0004`, qui vient après celle de l'étape 4
(`20260814_0003_journal_evenements`). Ne modifie jamais une migration déjà
appliquée.

---

## 3. Arborescence des fichiers à créer ou modifier

```text
auth/
|-- __init__.py
|-- models.py
|-- security.py
|-- dependencies.py
|-- schemas.py
`-- bootstrap.py
api/routers/
|-- auth.py               (nouveau)
`-- users.py               (nouveau)
alembic/versions/20260814_0004_utilisateurs.py   (nouveau)
main.py                                          (modifié)
api/routers/simulation.py                        (modifié)
requirements.txt                                 (modifié)

dashboard/src/
|-- auth/
|   |-- AuthContext.tsx
|   |-- LoginPage.tsx
|   `-- RequireRole.tsx
|-- components/UsersPage.tsx      (nouveau)
|-- services/api.ts                (modifié)
|-- App.tsx                        (modifié)
`-- components/Header.tsx          (modifié)
```

### Ajouter à `requirements.txt`

```text
# Hachage de mot de passe et jetons JWT pour l'authentification.
bcrypt==4.2.0
PyJWT==2.9.0
email-validator==2.2.0
```

```powershell
python -m pip install -r requirements.txt
```

---

## 4. Migration et modèle de la table utilisateurs

### 4.1 `alembic/versions/20260814_0004_utilisateurs.py`

```python
"""Ajoute la table des utilisateurs et de leurs rôles.

Revision ID: 20260814_0004
Revises: 20260814_0003
Create Date: 2026-08-18
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision = "20260814_0004"
down_revision = "20260814_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "TB_UTILISATEURS",
        sa.Column("UTILISATEUR_UUID", PostgreSQLUUID(as_uuid=True), primary_key=True),
        sa.Column("EMAIL", sa.String(150), nullable=False, unique=True),
        sa.Column("MOT_DE_PASSE_HASH", sa.String(255), nullable=False),
        sa.Column("NOM_COMPLET", sa.String(150), nullable=False),
        sa.Column("ROLE", sa.String(20), nullable=False),
        sa.Column("STATUT_ACTIF", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("DERNIERE_CONNEXION", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("DATE_CREATION", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_CREATION", sa.String(100), nullable=True),
        sa.Column("DATE_MODIFICATION", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("UTILISATEUR_ID_MODIFICATION", sa.String(100), nullable=True),
        sa.CheckConstraint(
            "\"ROLE\" IN ('administrateur', 'operateur', 'observateur')",
            name="ck_utilisateurs_role_valide",
        ),
    )
    op.create_index("ix_utilisateurs_email", "TB_UTILISATEURS", ["EMAIL"])


def downgrade() -> None:
    op.drop_index("ix_utilisateurs_email", table_name="TB_UTILISATEURS")
    op.drop_table("TB_UTILISATEURS")
```

Appliquer :

```powershell
python -m alembic upgrade head
python -m alembic current
```

**Résultat attendu :** `20260814_0004 (head)`.

### 4.2 `auth/models.py`

```python
"""Modèle SQLAlchemy de la table des utilisateurs."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base


class User(AuditMixin, Base):
    """Un compte utilisateur du dashboard, avec un rôle unique."""

    __tablename__ = "TB_UTILISATEURS"

    utilisateur_uuid: Mapped[uuid.UUID] = mapped_column(
        "UTILISATEUR_UUID", PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column("EMAIL", String(150), nullable=False, unique=True)
    mot_de_passe_hash: Mapped[str] = mapped_column("MOT_DE_PASSE_HASH", String(255), nullable=False)
    nom_complet: Mapped[str] = mapped_column("NOM_COMPLET", String(150), nullable=False)
    role: Mapped[str] = mapped_column("ROLE", String(20), nullable=False)
    statut_actif: Mapped[bool] = mapped_column("STATUT_ACTIF", Boolean, nullable=False, default=True)
    derniere_connexion: Mapped[TIMESTAMP | None] = mapped_column(
        "DERNIERE_CONNEXION", TIMESTAMP(timezone=True), nullable=True
    )
```

### 4.3 `auth/__init__.py`

```python
"""Authentification, rôles et gestion des utilisateurs."""
```

---

## 5. Sécurité : hachage et jetons JWT

### 5.1 `auth/security.py`

```python
"""Hachage de mot de passe et émission/lecture des jetons JWT."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

# En production, définir JWT_SECRET_KEY comme variable d'environnement --
# ne jamais garder la valeur par défaut ci-dessous hors développement local.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me-en-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8


def hash_password(mot_de_passe: str) -> str:
    """Hache un mot de passe en clair avec un sel bcrypt unique."""

    return bcrypt.hashpw(mot_de_passe.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(mot_de_passe: str, mot_de_passe_hash: str) -> bool:
    """Vérifie un mot de passe en clair contre son hachage stocké."""

    return bcrypt.checkpw(mot_de_passe.encode("utf-8"), mot_de_passe_hash.encode("utf-8"))


def create_access_token(email: str, role: str) -> str:
    """Émet un jeton JWT signé, valable ACCESS_TOKEN_EXPIRE_HOURS heures."""

    expiration = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": email, "role": role, "exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Décode et vérifie un jeton JWT. Lève jwt.PyJWTError si invalide/expiré."""

    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
```

### 5.2 `auth/dependencies.py`

```python
"""Dépendances FastAPI pour authentifier un utilisateur et vérifier son rôle."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import jwt

from app.database import get_database_session
from auth.models import User
from auth.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# Hiérarchie utilisée par require_role : un rôle donne accès à son niveau et
# à tout ce qui est en dessous (administrateur > operateur > observateur).
ROLE_HIERARCHY = {"observateur": 0, "operateur": 1, "administrateur": 2}


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_database_session),
) -> User:
    """Résout l'utilisateur courant à partir du jeton JWT envoyé par le client."""

    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Jeton invalide ou expiré, veuillez vous reconnecter.",
        ) from exc

    email = payload.get("sub")
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.statut_actif:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable ou compte désactivé.",
        )
    return user


def require_role(minimum_role: str):
    """Fabrique une dépendance qui exige au moins le rôle indiqué."""

    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if ROLE_HIERARCHY[current_user.role] < ROLE_HIERARCHY[minimum_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Votre rôle ne permet pas cette action.",
            )
        return current_user

    return checker
```

### 5.3 `auth/schemas.py`

```python
"""Schémas Pydantic de l'authentification et de la gestion des utilisateurs."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

VALID_ROLES = ("administrateur", "operateur", "observateur")


class LoginRequest(BaseModel):
    email: EmailStr
    mot_de_passe: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    nom_complet: str


class UserCreateRequest(BaseModel):
    email: EmailStr
    mot_de_passe: str = Field(min_length=8, description="8 caractères minimum.")
    nom_complet: str
    role: str


class UserUpdateRequest(BaseModel):
    nom_complet: str | None = None
    role: str | None = None
    statut_actif: bool | None = None
    nouveau_mot_de_passe: str | None = Field(default=None, min_length=8)


class UserOut(BaseModel):
    utilisateur_uuid: str
    email: EmailStr
    nom_complet: str
    role: str
    statut_actif: bool

    model_config = {"from_attributes": True}
```

---

## 6. Les routers `auth` et `users`

### 6.1 `api/routers/auth.py`

```python
"""Endpoint de connexion : vérifie les identifiants et émet un jeton JWT."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from auth.models import User
from auth.schemas import LoginRequest, TokenResponse
from auth.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["authentification"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, session: AsyncSession = Depends(get_database_session)
) -> TokenResponse:
    """Vérifie l'email et le mot de passe, renvoie un jeton JWT si valides."""

    result = await session.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not user.statut_actif or not verify_password(
        payload.mot_de_passe, user.mot_de_passe_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou mot de passe incorrect."
        )

    user.derniere_connexion = datetime.now(timezone.utc)
    await session.commit()

    token = create_access_token(email=user.email, role=user.role)
    return TokenResponse(access_token=token, role=user.role, nom_complet=user.nom_complet)
```

### 6.2 `api/routers/users.py`

Tous les endpoints ici exigent le rôle `administrateur` — c'est le rôle
minimum passé à `require_role`.

```python
"""Gestion des comptes utilisateurs -- réservé au rôle administrateur."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session
from auth.dependencies import require_role
from auth.models import User
from auth.schemas import VALID_ROLES, UserCreateRequest, UserOut, UserUpdateRequest
from auth.security import hash_password

router = APIRouter(
    prefix="/users",
    tags=["utilisateurs"],
    dependencies=[Depends(require_role("administrateur"))],
)


@router.get("", response_model=list[UserOut])
async def list_users(session: AsyncSession = Depends(get_database_session)) -> list[UserOut]:
    result = await session.execute(select(User).order_by(User.nom_complet))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest, session: AsyncSession = Depends(get_database_session)
) -> UserOut:
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"Rôle invalide. Attendu parmi {VALID_ROLES}.")

    existing = await session.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Un compte existe déjà avec cet email.")

    user = User(
        utilisateur_uuid=uuid.uuid4(),
        email=payload.email,
        mot_de_passe_hash=hash_password(payload.mot_de_passe),
        nom_complet=payload.nom_complet,
        role=payload.role,
        statut_actif=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{utilisateur_uuid}", response_model=UserOut)
async def update_user(
    utilisateur_uuid: uuid.UUID,
    payload: UserUpdateRequest,
    session: AsyncSession = Depends(get_database_session),
) -> UserOut:
    result = await session.execute(select(User).where(User.utilisateur_uuid == utilisateur_uuid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"Rôle invalide. Attendu parmi {VALID_ROLES}.")
        user.role = payload.role
    if payload.nom_complet is not None:
        user.nom_complet = payload.nom_complet
    if payload.statut_actif is not None:
        user.statut_actif = payload.statut_actif
    if payload.nouveau_mot_de_passe is not None:
        user.mot_de_passe_hash = hash_password(payload.nouveau_mot_de_passe)

    await session.commit()
    await session.refresh(user)
    return UserOut.model_validate(user)
```

### 6.3 Brancher les deux routers dans `main.py`

Ajouter, à côté des imports des routers existants :

```python
from api.routers import auth as auth_router
from api.routers import users as users_router
```

Puis, à côté des `app.include_router(...)` déjà présents (étape 5) :

```python
app.include_router(auth_router.router)
app.include_router(users_router.router)
```

---

## 7. Protéger les endpoints de pilotage déjà existants

Dans `api/routers/simulation.py` (étape 5), ajouter la dépendance de rôle sur
les trois endpoints qui modifient l'état du moteur. **Ne pas protéger**
`GET /simulation/status` : la lecture reste accessible à tous les rôles
connectés, y compris `observateur`.

```python
from auth.dependencies import require_role

# ... et sur chaque route qui modifie l'état :

@router.post("/simulation/start", response_model=SimulationStatusResponse,
             dependencies=[Depends(require_role("operateur"))])
async def start_simulation(...):
    ...

@router.post("/simulation/stop", response_model=SimulationStatusResponse,
             dependencies=[Depends(require_role("operateur"))])
async def stop_simulation(...):
    ...

@router.post("/simulation/speed", response_model=SimulationStatusResponse,
             dependencies=[Depends(require_role("operateur"))])
async def set_simulation_speed(...):
    ...
```

Rappel de la hiérarchie (section 5.2) : `require_role("operateur")` laisse
passer les administrateurs aussi — le rôle minimum, pas un rôle exact.

---

## 8. Créer le premier compte administrateur

**Pourquoi un script à part, plutôt qu'un mot de passe codé en dur dans le
seed :** un mot de passe par défaut connu de tous (même en développement)
est une mauvaise pratique qu'on évite dès maintenant.

### `auth/bootstrap.py`

```python
"""Crée le premier compte administrateur, de façon interactive.

Usage : python -m auth.bootstrap
"""
from __future__ import annotations

import asyncio
import getpass
import uuid

from sqlalchemy import select

from app.database import get_database_session
from auth.models import User
from auth.security import hash_password


async def _create_admin(email: str, mot_de_passe: str, nom_complet: str) -> None:
    async for session in get_database_session():
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"Un compte existe déjà pour {email}.")
            return

        user = User(
            utilisateur_uuid=uuid.uuid4(),
            email=email,
            mot_de_passe_hash=hash_password(mot_de_passe),
            nom_complet=nom_complet,
            role="administrateur",
            statut_actif=True,
        )
        session.add(user)
        await session.commit()
        print(f"Compte administrateur créé pour {email}.")


def main() -> None:
    email = input("Email de l'administrateur : ").strip()
    nom_complet = input("Nom complet : ").strip()
    mot_de_passe = getpass.getpass("Mot de passe (8 caractères minimum) : ")
    if len(mot_de_passe) < 8:
        print("Mot de passe trop court, opération annulée.")
        return
    asyncio.run(_create_admin(email, mot_de_passe, nom_complet))


if __name__ == "__main__":
    main()
```

Lancer une seule fois :

```powershell
python -m auth.bootstrap
```

---

## 9. Frontend : contexte d'authentification et page de connexion

### 9.1 `dashboard/src/auth/AuthContext.tsx`

```tsx
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Role = "administrateur" | "operateur" | "observateur";

interface AuthState {
  token: string | null;
  role: Role | null;
  nomComplet: string | null;
}

interface AuthContextValue extends AuthState {
  login: (email: string, motDePasse: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const STORAGE_KEY = "cmu_dashboard_auth";
const API_URL = import.meta.env.VITE_API_URL as string;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : { token: null, role: null, nomComplet: null };
  });

  useEffect(() => {
    if (state.token) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [state]);

  async function login(email: string, motDePasse: string) {
    const response = await fetch(`${API_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, mot_de_passe: motDePasse }),
    });
    if (!response.ok) {
      throw new Error("Email ou mot de passe incorrect.");
    }
    const data = await response.json();
    setState({ token: data.access_token, role: data.role, nomComplet: data.nom_complet });
  }

  function logout() {
    setState({ token: null, role: null, nomComplet: null });
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAuthenticated: state.token !== null }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé sous AuthProvider.");
  return context;
}
```

### 9.2 `dashboard/src/auth/LoginPage.tsx`

```tsx
import { useState, type FormEvent } from "react";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [erreur, setErreur] = useState<string | null>(null);
  const [enCours, setEnCours] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setErreur(null);
    setEnCours(true);
    try {
      await login(email, motDePasse);
    } catch {
      setErreur("Email ou mot de passe incorrect.");
    } finally {
      setEnCours(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>Simulateur CMU</h1>
        <p>Connexion au tableau de bord</p>
        <label>
          Email
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </label>
        <label>
          Mot de passe
          <input
            type="password"
            value={motDePasse}
            onChange={(e) => setMotDePasse(e.target.value)}
            required
          />
        </label>
        {erreur && <p className="login-error">{erreur}</p>}
        <button type="submit" disabled={enCours}>
          {enCours ? "Connexion..." : "Se connecter"}
        </button>
      </form>
    </div>
  );
}
```

### 9.3 `dashboard/src/auth/RequireRole.tsx`

Un composant utilitaire qui masque son contenu si le rôle connecté est
insuffisant — utilisé partout où une action ou un onglet doit rester
invisible pour certains rôles (section 11).

```tsx
import type { ReactNode } from "react";
import { useAuth } from "./AuthContext";

const HIERARCHY: Record<string, number> = { observateur: 0, operateur: 1, administrateur: 2 };

export function RequireRole({
  minimum,
  children,
}: {
  minimum: "administrateur" | "operateur" | "observateur";
  children: ReactNode;
}) {
  const { role } = useAuth();
  if (!role || HIERARCHY[role] < HIERARCHY[minimum]) return null;
  return <>{children}</>;
}
```

---

## 10. Frontend : onglet de gestion des utilisateurs

### `dashboard/src/components/UsersPage.tsx`

```tsx
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "../auth/AuthContext";

interface UserRow {
  utilisateur_uuid: string;
  email: string;
  nom_complet: string;
  role: string;
  statut_actif: boolean;
}

const API_URL = import.meta.env.VITE_API_URL as string;
const ROLES = ["administrateur", "operateur", "observateur"] as const;

export function UsersPage() {
  const { token } = useAuth();
  const [users, setUsers] = useState<UserRow[]>([]);
  const [email, setEmail] = useState("");
  const [nomComplet, setNomComplet] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [role, setRole] = useState<(typeof ROLES)[number]>("operateur");
  const [erreur, setErreur] = useState<string | null>(null);

  async function refresh() {
    const response = await fetch(`${API_URL}/users`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (response.ok) setUsers(await response.json());
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setErreur(null);
    const response = await fetch(`${API_URL}/users`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ email, mot_de_passe: motDePasse, nom_complet: nomComplet, role }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      setErreur(detail?.detail ?? "Impossible de créer l'utilisateur.");
      return;
    }
    setEmail("");
    setNomComplet("");
    setMotDePasse("");
    await refresh();
  }

  async function toggleActif(user: UserRow) {
    await fetch(`${API_URL}/users/${user.utilisateur_uuid}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ statut_actif: !user.statut_actif }),
    });
    await refresh();
  }

  return (
    <div className="users-page">
      <h2>Gestion des utilisateurs</h2>

      <table className="users-table">
        <thead>
          <tr>
            <th>Nom</th><th>Email</th><th>Rôle</th><th>Statut</th><th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.utilisateur_uuid}>
              <td>{u.nom_complet}</td>
              <td>{u.email}</td>
              <td>{u.role}</td>
              <td>{u.statut_actif ? "Actif" : "Désactivé"}</td>
              <td>
                <button onClick={() => toggleActif(u)}>
                  {u.statut_actif ? "Désactiver" : "Réactiver"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <form className="users-form" onSubmit={handleCreate}>
        <h3>Nouvel utilisateur</h3>
        <input placeholder="Nom complet" value={nomComplet} onChange={(e) => setNomComplet(e.target.value)} required />
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Mot de passe" value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} required minLength={8} />
        <select value={role} onChange={(e) => setRole(e.target.value as typeof role)}>
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        {erreur && <p className="login-error">{erreur}</p>}
        <button type="submit">Créer</button>
      </form>
    </div>
  );
}
```

---

## 11. Visibilité par rôle : ce que voit chaque acteur

| Élément du dashboard | Administrateur | Opérateur | Observateur |
|---|---|---|---|
| Cartes, graphiques, tableau (lecture) | ✅ | ✅ | ✅ |
| Bouton Démarrer / Arrêter / slider de vitesse | ✅ | ✅ | ❌ masqué |
| Onglet « Utilisateurs » | ✅ | ❌ masqué | ❌ masqué |
| Rapports (étape 9) | ✅ | ✅ | ❌ masqué (section rapports non affichée) |
| Injecteur d'anomalies (étape 10) | ✅ | ❌ masqué | ❌ masqué |

### Appliquer ça dans `App.tsx`

```tsx
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { RequireRole } from "./auth/RequireRole";
import { UsersPage } from "./components/UsersPage";
// ... les imports existants (Header, MetricCards, etc.)

function DashboardShell() {
  const { isAuthenticated } = useAuth();
  const [ongletActif, setOngletActif] = useState<"dashboard" | "utilisateurs">("dashboard");

  if (!isAuthenticated) return <LoginPage />;

  return (
    <KpiSocketProvider>
      <Header onNaviguer={setOngletActif} ongletActif={ongletActif} />
      {ongletActif === "dashboard" && (
        <main className="dashboard-grid">
          {/* MetricCards, graphiques, CenterLoadTable : inchangés */}
        </main>
      )}
      {ongletActif === "utilisateurs" && (
        <RequireRole minimum="administrateur">
          <UsersPage />
        </RequireRole>
      )}
    </KpiSocketProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <DashboardShell />
    </AuthProvider>
  );
}
```

### Ajuster `Header.tsx`

Enrober les contrôles Démarrer/Arrêter/vitesse existants avec
`<RequireRole minimum="operateur">`, et ajouter l'onglet « Utilisateurs »
enrobé avec `<RequireRole minimum="administrateur">`. Ajouter aussi un nom
d'utilisateur affiché + bouton de déconnexion (`useAuth().logout()`).

### Attacher le jeton à tous les appels REST existants

Dans `services/api.ts` (étape 5), chaque fonction (`getKpiSnapshot`,
`startSimulation`, etc.) doit maintenant envoyer l'en-tête
`Authorization: Bearer <token>`. Le plus simple : centraliser dans une seule
fonction d'appel :

```typescript
function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}
```

et l'utiliser dans chaque `fetch(...)` existant, en passant le token
récupéré via `useAuth()` dans chaque composant appelant.

---

## 12. Vérification

```powershell
python -m compileall auth api main.py
python -m alembic current
python -m auth.bootstrap
```

Test de connexion en ligne de commande :

```powershell
curl.exe -X POST http://127.0.0.1:8000/auth/login -H "Content-Type: application/json" -d '{"email":"ton_email","mot_de_passe":"ton_mot_de_passe"}'
```

**Résultat attendu :** un JSON avec `access_token`, `role: "administrateur"`.

Test qu'un endpoint protégé refuse sans jeton :

```powershell
curl.exe -X POST http://127.0.0.1:8000/simulation/start -H "Content-Type: application/json" -d '{"vitesse":60,"nombre_passages_simultanes_max":10}'
```

**Résultat attendu :** `401 Unauthorized`.

---

## 13. Checklist

- [ ] `20260814_0004 (head)` confirmé ;
- [ ] `python -m auth.bootstrap` a créé un compte administrateur fonctionnel ;
- [ ] `POST /auth/login` avec de bons identifiants renvoie un jeton ;
- [ ] `POST /simulation/start` sans jeton renvoie `401` ;
- [ ] un utilisateur `operateur` peut démarrer/arrêter mais pas créer d'utilisateur (`403` sur `/users`) ;
- [ ] un utilisateur `observateur` ne voit ni les boutons de pilotage ni l'onglet Utilisateurs ;
- [ ] la page de connexion s'affiche si aucun jeton valide n'est en mémoire ;
- [ ] le jeton persiste après un rafraîchissement de page (`localStorage`).

---

## 14. Dépannage

| Erreur | Cause probable | Solution |
|---|---|---|
| `401` alors que le mot de passe semble correct | Compte désactivé (`statut_actif = false`) | Vérifie via `/users` (en tant qu'admin) ou en base |
| `403` sur une route où le rôle devrait suffire | Mauvais rôle minimum passé à `require_role(...)` | Relis la hiérarchie section 5.2 |
| `ModuleNotFoundError: bcrypt` ou `jwt` | Dépendances pas installées dans `.venv` actif | `pip install -r requirements.txt` |
| Le token n'est jamais envoyé par le frontend | Header `Authorization` oublié dans un appel `fetch` | Vérifie chaque fonction de `services/api.ts` |
| `email-validator` manquant | Nécessaire pour `EmailStr` de Pydantic | Ajouté dans `requirements.txt` section 3, réinstaller |

---

## 15. Ce qui reste à faire (pas dans cette étape)

- Logo, bouton Arrêter déjà géré ici mais restylage visuel, remplacement du
  graphique → **étape 8**.
- Rapports PDF/Excel automatiques → **étape 9**.
- Injecteur d'anomalies configurable → **étape 10**.

**Fin du guide de l'étape 7.**
