package ru.proofforge.bridge

import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse

class ProofForgeApiClient(private val settings: ProofForgeSettings) {
    private val client = HttpClient.newHttpClient()

    fun listActiveTasks(): String {
        require(settings.userId.isNotBlank()) { "Proof Forge user id is required" }
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/practice-tasks?user_id=${settings.userId}&status=active"))
            .GET()
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }

    fun pair(ideProduct: String, pluginVersion: String): String {
        require(settings.userId.isNotBlank()) { "Proof Forge user id is required" }
        val json = """{"user_id":"${settings.userId}","ide":"jetbrains","ide_product":"$ideProduct","plugin_version":"$pluginVersion"}"""
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/ide-sessions/pair"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(json))
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }

    fun submit(taskId: String, payloadJson: String): String {
        val request = HttpRequest.newBuilder()
            .uri(URI.create("${settings.apiBaseUrl}/api/practice-tasks/$taskId/submissions"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(payloadJson))
            .build()
        return client.send(request, HttpResponse.BodyHandlers.ofString()).body()
    }
}
