package ru.proofforge.bridge

data class ProofForgeSettings(
    val apiBaseUrl: String = "https://api.proof-forge.ru",
    val apiKey: String = "",
    val userId: String = "",
    val ideSessionId: String = "",
)
