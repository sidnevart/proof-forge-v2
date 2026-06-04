package ru.proofforge.bridge

data class ProofForgeSettings(
    val apiBaseUrl: String = "http://localhost:8000",
    val userId: String = "",
    val ideSessionId: String = "",
)
