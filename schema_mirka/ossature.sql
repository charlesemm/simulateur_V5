-- DDL de l'ossature du simulateur : les 11 tables qui font tourner
-- l'application, par opposition aux tables metier reprises de Mirka.
--
-- FICHIER GENERE. Il n'a pas ete ecrit a la main : il a ete extrait par
-- pg_dump --schema-only d'une base ou les migrations 0001 a 0029 avaient ete
-- jouees, puis ou les 34 tables metier avaient ete supprimees. C'est donc le
-- DDL exact que produisait l'ancienne chaine de migrations, et non une
-- reconstitution.
--
-- La migration socle joue ces instructions une par une : asyncpg refuse
-- plusieurs instructions en un seul appel.

CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;

CREATE SEQUENCE public."SEQ_FACTURE_NUMERO"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 90000000
    CACHE 1;

CREATE TABLE public."TB_ANOMALIES_INJECTIONS" (
    "INJECTION_ID" uuid NOT NULL,
    "ANOMALIE_CODE" character varying(40) NOT NULL,
    "SIMULATION_ID" uuid,
    "PASSAGE_ID" character varying(64),
    "CIBLE_CLE" character varying(100),
    "VALEUR_ORIGINE" text,
    "VALEUR_INJECTEE" text,
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now(),
    "UTILISATEUR_ID_MODIFICATION" character varying(100)
);

CREATE TABLE public."TB_CAMPAGNES" (
    "CAMPAGNE_ID" uuid NOT NULL,
    "CAMPAGNE_REFERENCE" character varying(20) NOT NULL,
    "CAMPAGNE_LIBELLE" character varying(150) NOT NULL,
    "CAMPAGNE_STATUT" character varying(30) DEFAULT 'creee'::character varying NOT NULL,
    "CAMPAGNE_GRAINE" bigint NOT NULL,
    "CAMPAGNE_PALIER" character varying(20) NOT NULL,
    "CAMPAGNE_VOLUME_CIBLE" integer NOT NULL,
    "CAMPAGNE_PARAMETRES" jsonb DEFAULT '{}'::jsonb NOT NULL,
    "CAMPAGNE_DATE_FIN" timestamp with time zone,
    "UTILISATEUR_UUID" uuid,
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now(),
    "UTILISATEUR_ID_MODIFICATION" character varying(100),
    "CAMPAGNE_DATE_GENERATION" timestamp with time zone,
    "CAMPAGNE_LIGNES_GENEREES" integer DEFAULT 0 NOT NULL,
    "CAMPAGNE_ANOMALIES_POSEES" integer DEFAULT 0 NOT NULL,
    "CAMPAGNE_EMPREINTE" character varying(64),
    "CAMPAGNE_FICHIER" character varying(255),
    CONSTRAINT ck_campagnes_volume_positif CHECK (("CAMPAGNE_VOLUME_CIBLE" > 0))
);

CREATE TABLE public."TB_CAMPAGNES_CORRIGE" (
    "CAMPAGNE_ID" uuid NOT NULL,
    "CORRIGE_LIGNE" integer NOT NULL,
    "ANOMALIE_CODE" character varying(50) NOT NULL,
    "CORRIGE_CHAMP" character varying(60) NOT NULL,
    "CORRIGE_VALEUR_ORIGINE" text NOT NULL,
    "CORRIGE_VALEUR_INJECTEE" text NOT NULL,
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now(),
    "UTILISATEUR_ID_MODIFICATION" character varying(100)
);

CREATE TABLE public."TB_CAMPAGNES_ECHANGES" (
    "ECHANGE_ID" uuid NOT NULL,
    "CAMPAGNE_ID" uuid NOT NULL,
    "ECHANGE_ADRESSE" character varying(500) NOT NULL,
    "ECHANGE_DATE_ENVOI" timestamp with time zone NOT NULL,
    "ECHANGE_DATE_RECEPTION" timestamp with time zone,
    "ECHANGE_RESULTAT" character varying(20) NOT NULL,
    "ECHANGE_MOTIF_ECHEC" character varying(30),
    "ECHANGE_NOMBRE_CONSTATS" integer DEFAULT 0 NOT NULL,
    "ECHANGE_MESSAGE" text,
    "ECHANGE_RAPPORT" jsonb,
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now(),
    "UTILISATEUR_ID_MODIFICATION" character varying(100)
);

CREATE TABLE public."TB_CONFIG_ANOMALIES" (
    "CONFIG_ID" integer NOT NULL,
    "ENABLED" boolean NOT NULL,
    "RATE" numeric(3,2) NOT NULL,
    "SEVERITY" character varying(20) NOT NULL,
    "INJECTED_COUNT" integer NOT NULL,
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE public."TB_CONFIG_ANOMALIES_CONFIG_ID_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public."TB_CONFIG_ANOMALIES_CONFIG_ID_seq" OWNED BY public."TB_CONFIG_ANOMALIES"."CONFIG_ID";

CREATE TABLE public."TB_EVENEMENTS_METIER" (
    "EVENEMENT_ID" uuid NOT NULL,
    "TYPE_EVENEMENT" character varying(80) NOT NULL,
    "PASSAGE_ID" character varying(64) NOT NULL,
    "SIMULATED_AT" timestamp with time zone NOT NULL,
    "PAYLOAD" jsonb NOT NULL,
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone,
    "UTILISATEUR_ID_MODIFICATION" character varying(100),
    "SIMULATION_ID" uuid
);

CREATE TABLE public."TB_MDM_PAIRES" (
    "PAIRE_ID" uuid NOT NULL,
    "SIMULATION_ID" uuid,
    "PERSONNE_UUID_SOURCE" uuid NOT NULL,
    "PERSONNE_UUID_VARIANTE" uuid NOT NULL,
    "TYPE_VARIATION" character varying(40) NOT NULL,
    "MEME_PERSONNE" boolean DEFAULT true NOT NULL,
    "COMMENTAIRE" character varying(255),
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now(),
    "UTILISATEUR_ID_MODIFICATION" character varying(100)
);

CREATE TABLE public."TB_REFUS_ACCUEIL" (
    "REFUS_ID" uuid NOT NULL,
    "SIMULATION_ID" uuid,
    "PASSAGE_ID" character varying(64) NOT NULL,
    "PERSONNE_UUID" uuid NOT NULL,
    "REFUS_DATE" date NOT NULL,
    "REFUS_MOTIF" character varying(40) NOT NULL,
    "REGIME_CODE" character varying(30),
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now(),
    "UTILISATEUR_ID_MODIFICATION" character varying(100)
);

CREATE TABLE public."TB_REF_ANOMALIES" (
    "ANOMALIE_CODE" character varying(40) NOT NULL,
    "ANOMALIE_LIBELLE" character varying(150) NOT NULL,
    "ANOMALIE_FAMILLE" character varying(40) NOT NULL,
    "ANOMALIE_COULEUR" character varying(9) NOT NULL,
    "ANOMALIE_TABLE_CIBLE" character varying(80) NOT NULL,
    "ANOMALIE_COLONNE_CIBLE" character varying(80) NOT NULL,
    "ANOMALIE_SEVERITE" character varying(20) NOT NULL,
    "ANOMALIE_ACTIVE" boolean NOT NULL,
    "ANOMALIE_TAUX" numeric(3,2) NOT NULL,
    "ANOMALIE_DECLENCHEMENT" character varying(20) NOT NULL,
    "ANOMALIE_DELAI_SECONDES" integer,
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now(),
    "UTILISATEUR_ID_MODIFICATION" character varying(100)
);

CREATE TABLE public."TB_SIMULATIONS" (
    "SIMULATION_ID" uuid NOT NULL,
    "SIMULATION_LIBELLE" character varying(150) NOT NULL,
    "SIMULATION_STATUT" character varying(20) NOT NULL,
    "SIMULATION_PARAMETRES" jsonb NOT NULL,
    "SIMULATION_DATE_DEBUT" timestamp with time zone NOT NULL,
    "SIMULATION_DATE_FIN" timestamp with time zone,
    "UTILISATEUR_UUID" uuid,
    "PASSAGES_REUSSIS" integer DEFAULT 0 NOT NULL,
    "PASSAGES_ECHOUES" integer DEFAULT 0 NOT NULL,
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now(),
    "UTILISATEUR_ID_MODIFICATION" character varying(100),
    "SIMULATION_TYPE" character varying(20)
);

CREATE TABLE public."TB_UTILISATEURS" (
    "UTILISATEUR_UUID" uuid NOT NULL,
    "EMAIL" character varying(150) NOT NULL,
    "MOT_DE_PASSE_HASH" character varying(255) NOT NULL,
    "NOM_COMPLET" character varying(150) NOT NULL,
    "ROLE" character varying(20) NOT NULL,
    "STATUT_ACTIF" boolean DEFAULT true NOT NULL,
    "DERNIERE_CONNEXION" timestamp with time zone,
    "DATE_CREATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_CREATION" character varying(100),
    "DATE_MODIFICATION" timestamp with time zone DEFAULT now() NOT NULL,
    "UTILISATEUR_ID_MODIFICATION" character varying(100),
    "NOM_UTILISATEUR" character varying(80),
    "DOIT_CHANGER_MOT_DE_PASSE" boolean DEFAULT false NOT NULL,
    CONSTRAINT ck_utilisateurs_role_valide CHECK ((("ROLE")::text = ANY (ARRAY[('administrateur'::character varying)::text, ('operateur'::character varying)::text, ('observateur'::character varying)::text])))
);

ALTER TABLE ONLY public."TB_CONFIG_ANOMALIES" ALTER COLUMN "CONFIG_ID" SET DEFAULT nextval('public."TB_CONFIG_ANOMALIES_CONFIG_ID_seq"'::regclass);

ALTER TABLE ONLY public."TB_ANOMALIES_INJECTIONS"
    ADD CONSTRAINT "TB_ANOMALIES_INJECTIONS_pkey" PRIMARY KEY ("INJECTION_ID");

ALTER TABLE ONLY public."TB_CAMPAGNES"
    ADD CONSTRAINT "TB_CAMPAGNES_CAMPAGNE_REFERENCE_key" UNIQUE ("CAMPAGNE_REFERENCE");

ALTER TABLE ONLY public."TB_CAMPAGNES_CORRIGE"
    ADD CONSTRAINT "TB_CAMPAGNES_CORRIGE_pkey" PRIMARY KEY ("CAMPAGNE_ID", "CORRIGE_LIGNE", "ANOMALIE_CODE");

ALTER TABLE ONLY public."TB_CAMPAGNES_ECHANGES"
    ADD CONSTRAINT "TB_CAMPAGNES_ECHANGES_pkey" PRIMARY KEY ("ECHANGE_ID");

ALTER TABLE ONLY public."TB_CAMPAGNES"
    ADD CONSTRAINT "TB_CAMPAGNES_pkey" PRIMARY KEY ("CAMPAGNE_ID");

ALTER TABLE ONLY public."TB_CONFIG_ANOMALIES"
    ADD CONSTRAINT "TB_CONFIG_ANOMALIES_pkey" PRIMARY KEY ("CONFIG_ID");

ALTER TABLE ONLY public."TB_EVENEMENTS_METIER"
    ADD CONSTRAINT "TB_EVENEMENTS_METIER_pkey" PRIMARY KEY ("EVENEMENT_ID");

ALTER TABLE ONLY public."TB_MDM_PAIRES"
    ADD CONSTRAINT "TB_MDM_PAIRES_pkey" PRIMARY KEY ("PAIRE_ID");

ALTER TABLE ONLY public."TB_REFUS_ACCUEIL"
    ADD CONSTRAINT "TB_REFUS_ACCUEIL_pkey" PRIMARY KEY ("REFUS_ID");

ALTER TABLE ONLY public."TB_REF_ANOMALIES"
    ADD CONSTRAINT "TB_REF_ANOMALIES_pkey" PRIMARY KEY ("ANOMALIE_CODE");

ALTER TABLE ONLY public."TB_SIMULATIONS"
    ADD CONSTRAINT "TB_SIMULATIONS_pkey" PRIMARY KEY ("SIMULATION_ID");

ALTER TABLE ONLY public."TB_UTILISATEURS"
    ADD CONSTRAINT "TB_UTILISATEURS_EMAIL_key" UNIQUE ("EMAIL");

ALTER TABLE ONLY public."TB_UTILISATEURS"
    ADD CONSTRAINT "TB_UTILISATEURS_pkey" PRIMARY KEY ("UTILISATEUR_UUID");

ALTER TABLE ONLY public."TB_UTILISATEURS"
    ADD CONSTRAINT uq_utilisateurs_nom UNIQUE ("NOM_UTILISATEUR");

CREATE INDEX "IX_ANOMALIES_INJECTIONS_CODE" ON public."TB_ANOMALIES_INJECTIONS" USING btree ("ANOMALIE_CODE");

CREATE INDEX "IX_ANOMALIES_INJECTIONS_SIMULATION" ON public."TB_ANOMALIES_INJECTIONS" USING btree ("SIMULATION_ID");

CREATE INDEX "IX_CAMPAGNES_DATE_CREATION" ON public."TB_CAMPAGNES" USING btree ("DATE_CREATION");

CREATE INDEX "IX_CAMPAGNES_STATUT" ON public."TB_CAMPAGNES" USING btree ("CAMPAGNE_STATUT");

CREATE INDEX "IX_CORRIGE_ANOMALIE" ON public."TB_CAMPAGNES_CORRIGE" USING btree ("CAMPAGNE_ID", "ANOMALIE_CODE");

CREATE INDEX "IX_CORRIGE_CAMPAGNE" ON public."TB_CAMPAGNES_CORRIGE" USING btree ("CAMPAGNE_ID");

CREATE INDEX "IX_ECHANGES_CAMPAGNE" ON public."TB_CAMPAGNES_ECHANGES" USING btree ("CAMPAGNE_ID");

CREATE INDEX "IX_EVENEMENTS_DATE_CREATION" ON public."TB_EVENEMENTS_METIER" USING btree ("DATE_CREATION");

CREATE INDEX "IX_EVENEMENTS_METIER_SIMULATION" ON public."TB_EVENEMENTS_METIER" USING btree ("SIMULATION_ID");

CREATE INDEX "IX_EVENEMENTS_PASSAGE" ON public."TB_EVENEMENTS_METIER" USING btree ("PASSAGE_ID");

CREATE INDEX "IX_EVENEMENTS_SIMULATED_AT" ON public."TB_EVENEMENTS_METIER" USING btree ("SIMULATED_AT");

CREATE INDEX "IX_EVENEMENTS_TYPE" ON public."TB_EVENEMENTS_METIER" USING btree ("TYPE_EVENEMENT");

CREATE INDEX "IX_MDM_PAIRES_SIMULATION" ON public."TB_MDM_PAIRES" USING btree ("SIMULATION_ID");

CREATE INDEX "IX_MDM_PAIRES_SOURCE" ON public."TB_MDM_PAIRES" USING btree ("PERSONNE_UUID_SOURCE");

CREATE INDEX "IX_REFUS_ACCUEIL_PERSONNE" ON public."TB_REFUS_ACCUEIL" USING btree ("PERSONNE_UUID");

CREATE INDEX "IX_REFUS_ACCUEIL_SIMULATION" ON public."TB_REFUS_ACCUEIL" USING btree ("SIMULATION_ID");

CREATE INDEX "IX_SIMULATIONS_DATE_DEBUT" ON public."TB_SIMULATIONS" USING btree ("SIMULATION_DATE_DEBUT");

CREATE INDEX ix_utilisateurs_email ON public."TB_UTILISATEURS" USING btree ("EMAIL");

ALTER TABLE ONLY public."TB_ANOMALIES_INJECTIONS"
    ADD CONSTRAINT "TB_ANOMALIES_INJECTIONS_ANOMALIE_CODE_fkey" FOREIGN KEY ("ANOMALIE_CODE") REFERENCES public."TB_REF_ANOMALIES"("ANOMALIE_CODE");

ALTER TABLE ONLY public."TB_CAMPAGNES_CORRIGE"
    ADD CONSTRAINT fk_corrige_campagne FOREIGN KEY ("CAMPAGNE_ID") REFERENCES public."TB_CAMPAGNES"("CAMPAGNE_ID") ON DELETE CASCADE;

ALTER TABLE ONLY public."TB_CAMPAGNES_ECHANGES"
    ADD CONSTRAINT fk_echanges_campagne FOREIGN KEY ("CAMPAGNE_ID") REFERENCES public."TB_CAMPAGNES"("CAMPAGNE_ID") ON DELETE CASCADE;

ALTER TABLE ONLY public."TB_REFUS_ACCUEIL"
    ADD CONSTRAINT fk_refus_accueil_simulation FOREIGN KEY ("SIMULATION_ID") REFERENCES public."TB_SIMULATIONS"("SIMULATION_ID");

ALTER TABLE ONLY public."TB_EVENEMENTS_METIER"
    ADD CONSTRAINT fk_tb_evenements_metier_simulation FOREIGN KEY ("SIMULATION_ID") REFERENCES public."TB_SIMULATIONS"("SIMULATION_ID");

CREATE PUBLICATION dbz_publication_json WITH (publish = 'insert, update, delete, truncate');
