package ru.proofforge.bridge

import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse

class ProofForgeApiClient(private val settings: ProofForgeSettings) {
    private val client = HttpClient.newHttpClient()

    private fun apiKeyHeader(): String {
        require(settings.apiKey.isNotBlank()) {
            "Proof Forge API key is required. Generate one in Dashboard → Settings → API Keys."
        }
        return settings.apiKey
    }

    fun listActiveTasks(): String {
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/practice-tasks?user_id=${settings.userId}&status=active"))
            .header("X-Api-Key", apiKeyHeader())
            .GET()
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }

    fun pair(ideProduct: String, pluginVersion: String): String {
        val json = """{"user_id":"${settings.userId}","ide":"jetbrains","ide_product":"$ideProduct","plugin_version":"$pluginVersion"}"""
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/ide-sessions/pair"))
            .header("Content-Type", "application/json")
            .header("X-Api-Key", apiKeyHeader())
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }

    fun submit(taskId: String, payloadJson: String): String {
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/practice-tasks/$taskId/submissions"))
            .header("Content-Type", "application/json")
            .header("X-Api-Key", apiKeyHeader())
            .POST(HttpRequest.BodyPublishers.ofString(payloadJson))
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }
}
