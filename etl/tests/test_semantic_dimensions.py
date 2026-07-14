import unittest

import pandas as pd

from src.staging.stg_semantic_dimensions import enrich_semantic_dimensions
from src.staging.stg_normalize_columns import normalize_dataframe
from src.utils.logger import global_logger


class SemanticDimensionsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global_logger.disabled = True

    @classmethod
    def tearDownClass(cls):
        global_logger.disabled = False

    def setUp(self):
        self.frame = pd.DataFrame([
            {
                "fuente": "github",
                "plataforma": "github",
                "nombre_agente": "Cline",
                "categoria": "produccion_tecnica",
                "titulo": "Agente para repositorios",
                "texto": "Automatización de cambios",
                "tecnologia_raw": "Python",
                "comunidad_raw": "acme-ai",
                "tipo_comunidad_raw": "Organization",
            },
            {
                "fuente": "catalogo",
                "plataforma": "aidedev_ai_coding",
                "nombre_agente": "Claude Code",
                "categoria": "actividad_tecnica",
                "titulo": "Agente - owner/repo",
                "texto": "dataset=AIDev; language=TypeScript",
                "tecnologia_raw": "TypeScript",
                "comunidad_raw": "owner",
                "tipo_comunidad_raw": "organización o propietario de repositorio",
            },
            {
                "fuente": "stackoverflow",
                "plataforma": "stackoverflow",
                "categoria": "actividad_tecnica",
                "titulo": "Integrar un agente en React con VS Code",
                "texto": "Pregunta técnica",
                "tecnologia_raw": "reactjs, artificial-intelligence",
                "comunidad_raw": "Stack Overflow",
                "tipo_comunidad_raw": "Q&A técnica",
            },
            {
                "fuente": "gnews",
                "plataforma": "google_news",
                "categoria": "actividad_tecnica",
                "titulo": "AI coding market update",
                "texto": "",
                "comunidad_raw": "Reuters",
                "tipo_comunidad_raw": "medio o fuente editorial",
            },
            {
                "fuente": "fuente_propia",
                "plataforma": "encuesta_upse",
                "categoria": "adopcion_academica",
                "titulo": "Encuesta institucional",
                "texto": "actividad=programación",
                "comunidad_raw": "Comunidad UPSE",
                "tipo_comunidad_raw": "comunidad académica",
                "region_comunidad_raw": "Ecuador",
            },
        ])

    def test_structured_metadata_populates_real_dimensions(self):
        result = enrich_semantic_dimensions(self.frame)

        self.assertEqual(result.loc[0, "dim_nombre_plataforma"], "VS Code")
        self.assertEqual(result.loc[0, "dim_nombre_tecnologia"], "Python")
        self.assertEqual(result.loc[0, "dim_nombre_comunidad"], "acme-ai")
        self.assertEqual(result.loc[0, "dim_tecnologia_metodo"], "metadata_estructurada")

        self.assertEqual(result.loc[1, "dim_nombre_plataforma"], "Terminal / CLI")
        self.assertEqual(result.loc[1, "dim_nombre_tecnologia"], "TypeScript")
        self.assertEqual(result.loc[1, "dim_nombre_comunidad"], "owner")

    def test_contextual_rule_is_used_when_structured_technology_is_absent(self):
        row = self.frame.iloc[[2]].copy()
        row["tecnologia_raw"] = ""
        result = enrich_semantic_dimensions(row)

        self.assertEqual(result.iloc[0]["dim_nombre_tecnologia"], "React")
        self.assertEqual(result.iloc[0]["dim_tecnologia_metodo"], "regla_contextual")
        self.assertEqual(result.iloc[0]["dim_nombre_plataforma"], "VS Code")
        self.assertEqual(result.iloc[0]["dim_plataforma_metodo"], "regla_contextual")

    def test_source_is_not_reused_as_platform(self):
        row = self.frame.iloc[[3]].copy()
        result = enrich_semantic_dimensions(row)

        self.assertEqual(result.iloc[0]["fuente"], "gnews")
        self.assertEqual(result.iloc[0]["plataforma"], "No determinada")
        self.assertEqual(result.iloc[0]["dim_nombre_plataforma"], "No determinada")
        self.assertEqual(result.iloc[0]["dim_plataforma_metodo"], "sin_evidencia")

    def test_unknown_technology_is_explicit_instead_of_recycling_category(self):
        result = enrich_semantic_dimensions(self.frame)

        self.assertEqual(result.loc[3, "dim_nombre_tecnologia"], "No determinada")
        self.assertNotEqual(result.loc[3, "dim_nombre_tecnologia"], result.loc[3, "categoria"])
        self.assertEqual(result.loc[3, "dim_nombre_comunidad"], "Reuters")

    def test_academic_community_keeps_region(self):
        result = enrich_semantic_dimensions(self.frame)

        self.assertEqual(result.loc[4, "dim_nombre_plataforma"], "No determinada")
        self.assertEqual(result.loc[4, "dim_nombre_comunidad"], "Comunidad UPSE")
        self.assertEqual(result.loc[4, "dim_region_comunidad"], "Ecuador")

    def test_github_normalization_preserves_language_and_owner(self):
        raw = pd.DataFrame([{
            "id": 1,
            "name": "agent-repo",
            "description": "Python agent",
            "language": "Python",
            "owner": {"login": "open-source-lab", "type": "Organization"},
        }])
        normalized = normalize_dataframe(raw, {"fuente": "github", "tipo_fuente": "api", "id": 10})

        self.assertEqual(normalized.loc[0, "tecnologia_raw"], "Python")
        self.assertEqual(normalized.loc[0, "comunidad_raw"], "open-source-lab")
        self.assertEqual(normalized.loc[0, "tipo_comunidad_raw"], "Organization")

    def test_stackoverflow_normalization_preserves_tags(self):
        raw = pd.DataFrame([{
            "id": "42",
            "title": "React integration",
            "description": "Question body",
            "tags": ["reactjs", "artificial-intelligence"],
            "score": 2,
            "answer_count": 3,
        }])
        normalized = normalize_dataframe(raw, {"fuente": "stackoverflow", "tipo_fuente": "api", "id": 11})

        self.assertEqual(normalized.loc[0, "tecnologia_raw"], "reactjs, artificial-intelligence")
        self.assertEqual(normalized.loc[0, "comunidad_raw"], "Stack Overflow")


if __name__ == "__main__":
    unittest.main()
