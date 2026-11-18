import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gestao_demandas import banco, relatorios, servicos
from gestao_demandas.models import Andamento, FormDemanda


class TestFluxoDemanda(unittest.TestCase):
    def setUp(self):
        self.conn = banco.conectar_em(":memory:")

    def tearDown(self):
        self.conn.close()

    def test_cria_e_atualiza_acao_necessaria(self):
        form = FormDemanda(
            titulo="Responder solicitação",
            tipo_atendimento="Responder",
            status="Aguardando resposta",
        )
        demanda_id = servicos.criar_demanda(self.conn, form, "manual")

        demanda = servicos.obter_demanda(self.conn, demanda_id)
        self.assertEqual(demanda.tipo_atendimento, "Responder")
        self.assertEqual(demanda.status, "Aguardando resposta")

        form.tipo_atendimento = "Encaminhar e responder"
        form.status = "Encaminhada"
        servicos.atualizar_demanda(self.conn, demanda_id, form)

        atualizada = servicos.obter_demanda(self.conn, demanda_id)
        self.assertEqual(atualizada.tipo_atendimento, "Encaminhar e responder")
        self.assertEqual(atualizada.status, "Encaminhada")
        self.assertTrue(
            any("tipo_atendimento" in item.acao for item in servicos.historico(self.conn, demanda_id))
        )

    def test_registra_andamento_na_linha_do_tempo(self):
        demanda_id = servicos.criar_demanda(
            self.conn, FormDemanda(titulo="Demanda de teste"), "manual"
        )
        andamento_id = servicos.registrar_andamento(
            self.conn,
            demanda_id,
            "Encaminhamento",
            "Solicitação enviada para análise.",
            "Equipe técnica",
        )

        andamentos = servicos.listar_andamentos(self.conn, demanda_id)
        self.assertEqual(len(andamentos), 1)
        self.assertEqual(andamentos[0].id, andamento_id)
        self.assertEqual(andamentos[0].destinatario, "Equipe técnica")

    def test_rejeita_andamento_sem_descricao(self):
        demanda_id = servicos.criar_demanda(
            self.conn, FormDemanda(titulo="Demanda de teste"), "manual"
        )
        with self.assertRaisesRegex(ValueError, "Descreva"):
            servicos.registrar_andamento(
                self.conn, demanda_id, "Nota interna", "  "
            )

    def test_registra_movimento_com_data_destino_e_observacao(self):
        demanda_id = servicos.criar_demanda(
            self.conn, FormDemanda(titulo="Demanda de teste"), "manual"
        )
        servicos.registrar_movimento(
            self.conn,
            demanda_id,
            "2026-10-12",
            "Secretaria de análise",
            "Encaminhado para avaliação.",
        )
        servicos.registrar_movimento(
            self.conn, demanda_id, "2026-10-14", "Gabinete"
        )

        andamentos = servicos.listar_andamentos(self.conn, demanda_id)
        self.assertEqual(andamentos[0].momento, "2026-10-12")
        self.assertEqual(andamentos[0].tipo, "Encaminhamento")
        self.assertEqual(andamentos[0].destinatario, "Secretaria de análise")
        self.assertEqual(andamentos[0].descricao, "Encaminhado para avaliação.")
        self.assertEqual(andamentos[1].momento, "2026-10-14")
        self.assertEqual(andamentos[1].destinatario, "Gabinete")
        self.assertEqual(andamentos[1].descricao, "")

    def test_rejeita_movimento_sem_data_valida_ou_destino(self):
        demanda_id = servicos.criar_demanda(
            self.conn, FormDemanda(titulo="Demanda de teste"), "manual"
        )
        with self.assertRaisesRegex(ValueError, "data de movimentação"):
            servicos.registrar_movimento(self.conn, demanda_id, "data inválida", "Gabinete")
        with self.assertRaisesRegex(ValueError, "destino"):
            servicos.registrar_movimento(self.conn, demanda_id, "2026-10-12", " ")

    def test_exporta_historico_movimentacoes_em_html(self):
        andamento = Andamento(
            momento="2026-10-12",
            destinatario="Setor <análise>",
            descricao="Encaminhado & aguardando resposta",
        )
        with tempfile.TemporaryDirectory() as pasta:
            with patch(
                "gestao_demandas.relatorios.config.get_relatorios_dir",
                return_value=Path(pasta),
            ):
                caminho = relatorios.exportar_historico_html(
                    12, "Demanda <teste>", [andamento]
                )

            conteudo = caminho.read_text(encoding="utf-8")
            self.assertIn("<th>Data do Movimento</th>", conteudo)
            self.assertIn("<th>Destino</th>", conteudo)
            self.assertIn("<th>Observação</th>", conteudo)
            self.assertIn("12/10/2026", conteudo)
            self.assertIn("Setor &lt;análise&gt;", conteudo)
            self.assertIn("Encaminhado &amp; aguardando resposta", conteudo)
            self.assertIn("Demanda &lt;teste&gt;", conteudo)

    def test_migra_banco_antigo_com_acao_padrao(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "antigo.db"
            conn = sqlite3.connect(caminho)
            conn.execute(
                "CREATE TABLE demandas ("
                "id INTEGER PRIMARY KEY, titulo TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'Novo', prazo TEXT)"
            )
            conn.commit()
            conn.close()

            migrado = banco.conectar_em(caminho)
            colunas = {
                linha["name"]
                for linha in migrado.execute("PRAGMA table_info(demandas)")
            }
            self.assertIn("tipo_atendimento", colunas)
            self.assertEqual(
                migrado.execute(
                    "SELECT dflt_value FROM pragma_table_info('demandas') "
                    "WHERE name = 'tipo_atendimento'"
                ).fetchone()[0],
                "'Encaminhar'",
            )
            migrado.close()


if __name__ == "__main__":
    unittest.main()
