import unittest
from unittest import mock


class LookoverCodexSDKTests(unittest.TestCase):
    def test_langchain_callback_handler_uses_codex_runtime_client(self) -> None:
        with mock.patch("lookover_codex_sdk.langchain.callback.RuntimeClient") as runtime_client:
            from lookover_codex_sdk.langchain import LookoverCallbackHandler

            handler = LookoverCallbackHandler(
                api_key="ignored",
                agent_id="agent_01_simple_llm_chain",
                agent_version="1.0.0",
                base_url="http://localhost:8080",
                model_provider="ollama",
                model_version="llama3.2",
            )

        runtime_client.assert_called_once_with("http://localhost:8080")
        self.assertTrue(hasattr(handler, "on_llm_start"))
        self.assertTrue(hasattr(handler, "on_llm_end"))

    def test_langgraph_listener_wraps_graph_and_returns_result(self) -> None:
        fake_client = mock.Mock()
        fake_wrapper = mock.Mock()
        fake_wrapper.invoke.return_value = {"messages": ["ok"]}

        with mock.patch("lookover_codex_sdk.langgraph.listener.RuntimeClient", return_value=fake_client) as runtime_client:
            with mock.patch("lookover_codex_sdk.langgraph.listener.wrap_langgraph", return_value=fake_wrapper) as wrap_langgraph:
                from lookover_codex_sdk.langgraph import LookoverLangGraphListener

                listener = LookoverLangGraphListener(
                    api_key="ignored",
                    agent_id="agent_12_supervisor",
                    agent_version="1.0.0",
                    model_provider="googleai",
                    model_version="gemini-2.0-flash",
                    base_url="http://localhost:8080",
                )
                graph = mock.Mock()

                result = listener.invoke(graph, {"messages": ["hello"]}, {"recursion_limit": 8})

        runtime_client.assert_called_once_with("http://localhost:8080")
        wrap_langgraph.assert_called_once()
        fake_wrapper.invoke.assert_called_once_with({"messages": ["hello"]}, {"recursion_limit": 8})
        self.assertEqual(result, {"messages": ["ok"]})


if __name__ == "__main__":
    unittest.main()
