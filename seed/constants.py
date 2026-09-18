"""Centralise les libellés métier plausibles utilisés par le seed CMU."""

# Les localités permettent de répartir les centres sur le territoire ivoirien.
IVORIAN_CITIES = [
    "Abidjan-Cocody", "Abidjan-Yopougon", "Abidjan-Abobo", "Abidjan-Treichville",
    "Abidjan-Port-Bouët", "Bouaké", "Yamoussoukro", "San-Pédro", "Korhogo",
    "Daloa", "Man", "Gagnoa", "Abengourou", "Bondoukou", "Divo",
]

# Les six premiers types sont les historiques du simulateur ; les suivants
# viennent de la liste publique des établissements CNAM (seed/donnees), dont
# le type se lit dans le nom. Codes mnémoniques, pas des compteurs : la règle
# « aucun numéro consécutif » ne les concerne pas.
HEALTH_CENTER_TYPES = [
    ("HG", "Hôpital général"),
    ("CHR", "Centre hospitalier régional"),
    ("CSU", "Centre de santé urbain"),
    ("CSR", "Centre de santé rural"),
    ("CLN", "Clinique médicale"),
    ("PMI", "Centre de protection maternelle et infantile"),
    ("CHU", "Centre hospitalier universitaire"),
    ("DISP", "Dispensaire"),
    ("SSSU", "Service de santé scolaire et universitaire"),
    ("CS", "Centre de santé"),
    ("MAT", "Maternité"),
    ("CAT", "Centre antituberculeux"),
    ("INST", "Institut spécialisé"),
    ("MIL", "Centre de santé des forces de défense et de sécurité"),
    ("CMS", "Centre médico-social"),
    ("FSU", "Formation sanitaire urbaine"),
    ("HOP", "Hôpital confessionnel ou municipal"),
    ("AUT", "Autre établissement sanitaire"),
]

# Ces noms complètent Faker avec une représentation ivoirienne identifiable.
IVORIAN_LAST_NAMES = [
    "Kouassi", "Yao", "Koné", "Ouattara", "Traoré", "Bamba", "N'Guessan",
    "Koffi", "Aka", "Amani", "Kouamé", "Diabaté", "Fofana", "Touré", "Soro",
    "Coulibaly", "Gnahoré", "Dago", "Zadi", "Assi", "Bakayoko", "Kouadio",
    "N'Dri", "Guei", "Doumbia", "Kanga", "Aké", "Brou", "Adjoumani", "Yapi",
]

IVORIAN_FIRST_NAMES = [
    "Aïssata", "Aminata", "Aya", "Fatoumata", "Mariame", "Nafissatou",
    "Affoué", "Akissi", "Amenan", "Awa", "Mariam", "Grâce", "Kady", "Mawa",
    "Adama", "Bakary", "Brahima", "Cheick", "Daouda", "Didier", "Ibrahim",
    "Ismaël", "Jean-Marc", "Kader", "Karim", "Mamadou", "Moussa", "Oumar",
    "Serge", "Souleymane",
]

MEDICAL_SPECIALTIES = [
    ("GEN", "Médecine générale"), ("PED", "Pédiatrie"),
    ("GYN", "Gynécologie-obstétrique"), ("DEN", "Odontostomatologie"),
    ("RAD", "Radiologie et imagerie médicale"), ("CAR", "Cardiologie"),
    ("DER", "Dermatologie"), ("ORL", "Oto-rhino-laryngologie"),
    ("OPH", "Ophtalmologie"), ("CHI", "Chirurgie générale"),
    ("MIR", "Médecine interne"), ("INF", "Maladies infectieuses"),
    ("NEU", "Neurologie"), ("PNE", "Pneumologie"),
    ("GAS", "Gastro-entérologie"), ("URO", "Urologie"),
    ("END", "Endocrinologie-diabétologie"), ("RHU", "Rhumatologie"),
]

# Cent pathologies courantes, classées en dix familles de dix codes.
PATHOLOGY_LABELS = [
    "Paludisme simple", "Paludisme grave", "Fièvre typhoïde", "Dengue",
    "Infection à VIH", "Tuberculose pulmonaire", "Hépatite virale B",
    "Hépatite virale C", "Amibiase intestinale", "Schistosomiase",
    "Rhinopharyngite aiguë", "Angine aiguë", "Sinusite aiguë", "Otite moyenne",
    "Bronchite aiguë", "Pneumonie communautaire", "Asthme bronchique",
    "Bronchopneumopathie chronique", "Grippe saisonnière", "COVID-19",
    "Hypertension artérielle", "Insuffisance cardiaque", "Cardiopathie ischémique",
    "Trouble du rythme cardiaque", "Accident vasculaire cérébral",
    "Thrombose veineuse profonde", "Artériopathie périphérique", "Péricardite",
    "Cardiomyopathie", "Hypotension artérielle",
    "Diabète de type 1", "Diabète de type 2", "Hypoglycémie",
    "Dyslipidémie", "Obésité", "Goitre thyroïdien", "Hyperthyroïdie",
    "Hypothyroïdie", "Malnutrition aiguë", "Carence en vitamine D",
    "Gastro-entérite aiguë", "Reflux gastro-œsophagien", "Gastrite",
    "Ulcère gastroduodénal", "Constipation", "Diarrhée infectieuse",
    "Hémorroïdes", "Hernie inguinale", "Appendicite aiguë", "Lithiase biliaire",
    "Infection urinaire", "Pyélonéphrite", "Insuffisance rénale aiguë",
    "Maladie rénale chronique", "Lithiase urinaire", "Hypertrophie prostatique",
    "Prostatite", "Syndrome néphrotique", "Incontinence urinaire", "Vaginite",
    "Anémie ferriprive", "Drépanocytose", "Anémie palustre", "Leucopénie",
    "Thrombopénie", "Trouble de la coagulation", "Leucémie", "Lymphome",
    "Carence en folates", "Anémie mégaloblastique",
    "Dermatite atopique", "Eczéma de contact", "Urticaire", "Gale",
    "Teigne", "Impétigo", "Abcès cutané", "Acné", "Mycose cutanée", "Psoriasis",
    "Arthrose du genou", "Lombalgie commune", "Cervicalgie", "Arthrite",
    "Goutte", "Fracture fermée", "Entorse de cheville", "Tendinite",
    "Sciatique", "Ostéomyélite",
    "Conjonctivite", "Cataracte", "Glaucome", "Carie dentaire",
    "Gingivite", "Parodontite", "Migraine", "Épilepsie",
    "Trouble anxieux", "Dépression",
]

# Les médicaments ne sont plus inventés ici : ils viennent de la liste CMU
# publiée par la CNAM (seed/donnees/medicaments_cmu.csv).

# Vingt médecins conseils, au niveau central. Les agents d'accueil, eux,
# suivent le nombre d'établissements : un par centre (seed/runner.py).
MEDECINS_CONSEILS = 20

INVOICE_TYPES = [
    ("AMB", "Soins ambulatoires"), ("DEN", "Soins dentaires"),
    ("BIO", "Biologie et imagerie"), ("HOS", "Hospitalisation"),
    ("PHA", "Pharmacie"),
]

MEDICAL_ACTS = [
    ("CONS-GEN", "Consultation généraliste", "consultation", "AMB", 5000),
    ("CONS-SPE", "Consultation spécialiste", "consultation", "AMB", 10000),
    ("DENT-DET", "Détartrage dentaire", "dentaire", "DEN", 15000),
    ("DENT-EXT", "Extraction dentaire", "dentaire", "DEN", 20000),
    ("DENT-CAR", "Traitement d'une carie", "dentaire", "DEN", 18000),
    ("BIO-NFS", "Numération formule sanguine", "biologie", "BIO", 5000),
    ("BIO-GLY", "Glycémie", "biologie", "BIO", 2500),
    ("BIO-CRE", "Créatininémie", "biologie", "BIO", 3500),
    ("BIO-URE", "Urémie", "biologie", "BIO", 3500),
    ("BIO-TRA", "Transaminases", "biologie", "BIO", 6000),
    ("BIO-CRP", "Protéine C-réactive", "biologie", "BIO", 6000),
    ("BIO-GEU", "Goutte épaisse paludisme", "biologie", "BIO", 3000),
    ("BIO-URI", "Examen cytobactériologique des urines", "biologie", "BIO", 7000),
    ("BIO-SEL", "Sérologie VIH", "biologie", "BIO", 4000),
    ("BIO-HBS", "Antigène HBs", "biologie", "BIO", 7000),
    ("BIO-LIP", "Bilan lipidique", "biologie", "BIO", 9000),
    ("BIO-HBA", "Hémoglobine glyquée", "biologie", "BIO", 9000),
    ("BIO-GRO", "Groupage sanguin et rhésus", "biologie", "BIO", 5000),
    ("IMG-RAD", "Radiographie standard", "imagerie", "BIO", 15000),
    ("IMG-ECH", "Échographie", "imagerie", "BIO", 25000),
    ("IMG-MAM", "Mammographie", "imagerie", "BIO", 30000),
    ("IMG-SCA", "Scanner", "imagerie", "BIO", 80000),
    ("IMG-IRM", "Imagerie par résonance magnétique", "imagerie", "BIO", 150000),
    ("HOS-MED", "Hospitalisation en médecine générale", "hospitalisation", "HOS", 25000),
    ("HOS-CHI", "Hospitalisation en chirurgie", "hospitalisation", "HOS", 40000),
    ("HOS-MAT", "Hospitalisation en maternité", "hospitalisation", "HOS", 30000),
    ("HOS-PED", "Hospitalisation en pédiatrie", "hospitalisation", "HOS", 25000),
    ("HOS-REA", "Hospitalisation en réanimation", "hospitalisation", "HOS", 100000),
    ("URG-ACC", "Accueil et prise en charge aux urgences", "urgence", "AMB,HOS", 15000),
    ("SOI-PAN", "Pansement simple", "soin", "AMB", 3000),
]


# --------------------------------------------------------------------------
# Référentiels provisoires -- à remplacer par les valeurs réelles du système
# CNAM dès qu'elles seront disponibles. Seuls les codes sont provisoires :
# la structure, elle, est celle des tables d'origine.
# --------------------------------------------------------------------------

# TYPE_IDENTIFIANT_CODE est un VARCHAR2(6) : aucun code ne peut dépasser
# six caractères.
TYPES_IDENTIFIANTS = [
    ("NNI", "Numéro national d'identification"),
    ("CNI", "Carte nationale d'identité"),
    ("RECEP", "Récépissé d'enrôlement"),
    ("CMU", "Numéro d'assuré CMU"),
    ("PASSPT", "Passeport"),
    ("ATTEST", "Attestation d'identité"),
]

# Le troisième champ porte le régime auquel la profession donne droit :
# RAM pour l'assistance médicale (100 %), RGB pour le régime général (70 %).
PROFESSIONS = [
    ("SALPR", "Salarié du secteur privé", "RGB"),
    ("SALPU", "Salarié du secteur public", "RGB"),
    ("FONCT", "Fonctionnaire", "RGB"),
    ("RETRA", "Retraité", "RGB"),
    ("INDEP", "Travailleur indépendant", "RGB"),
    ("COMMR", "Commerçant", "RGB"),
    ("ARTIS", "Artisan", "RGB"),
    ("AGRIC", "Agriculteur", "RGB"),
    ("PECHE", "Pêcheur", "RGB"),
    ("TRANS", "Transporteur", "RGB"),
    ("ENSEI", "Enseignant", "RGB"),
    ("SANTE", "Personnel de santé", "RGB"),
    ("ETUDI", "Étudiant", "RAM"),
    ("ELEVE", "Élève", "RAM"),
    ("ENFAN", "Enfant à charge", "RAM"),
    ("MENAG", "Personne au foyer", "RAM"),
    ("APPRE", "Apprenti", "RAM"),
    ("SANSE", "Sans emploi", "RAM"),
    ("INDIG", "Personne indigente", "RAM"),
    ("AUTRE", "Autre situation", "RAM"),
]

# Le code numérique 384 est celui, réel, de la Côte d'Ivoire (norme ISO
# 3166-1) -- sans lien avec le préfixe du numéro de sécurité sociale simulé
# (394, seed/runner.py:numero_securite_sociale), qui lui est arbitraire.
# (code, continent, numérique, dénomination, gentilé, indicatif, devise, lat, lon)
COUNTRIES = [
    ("CIV", "AF", 384, "Côte d'Ivoire", "Ivoirienne", 225, "XOF", 7.54, -5.55),
    ("BFA", "AF", 854, "Burkina Faso", "Burkinabè", 226, "XOF", 12.24, -1.56),
    ("MLI", "AF", 466, "Mali", "Malienne", 223, "XOF", 17.57, -3.99),
    ("GIN", "AF", 324, "Guinée", "Guinéenne", 224, "GNF", 9.95, -9.70),
    ("GHA", "AF", 288, "Ghana", "Ghanéenne", 233, "GHS", 7.95, -1.02),
    ("LBR", "AF", 430, "Liberia", "Libérienne", 231, "LRD", 6.43, -9.43),
    ("SEN", "AF", 686, "Sénégal", "Sénégalaise", 221, "XOF", 14.50, -14.45),
    ("FRA", "EU", 250, "France", "Française", 33, "EUR", 46.23, 2.21),
]

# Les quatorze districts de Côte d'Ivoire, avec leurs coordonnées
# approximatives : ils serviront de niveau « région ».
IVORIAN_DISTRICTS = [
    ("Abidjan", 5.35, -4.02),
    ("Yamoussoukro", 6.82, -5.28),
    ("Bas-Sassandra", 5.20, -6.30),
    ("Comoé", 5.85, -3.20),
    ("Denguélé", 9.75, -7.55),
    ("Gôh-Djiboua", 6.15, -5.95),
    ("Lacs", 6.90, -4.30),
    ("Lagunes", 5.85, -4.55),
    ("Montagnes", 7.40, -7.55),
    ("Sassandra-Marahoué", 6.90, -6.45),
    ("Savanes", 9.45, -5.63),
    ("Vallée du Bandama", 7.70, -5.03),
    ("Woroba", 8.45, -6.60),
    ("Zanzan", 8.05, -3.20),
]
