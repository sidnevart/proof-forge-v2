plugins {
    kotlin("jvm") version "2.1.21"
    id("org.jetbrains.intellij.platform") version "2.7.2"
}

group = "ru.proofforge"
version = "0.1.0"

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

dependencies {
    intellijPlatform {
        intellijIdeaCommunity("2025.1.2")
        bundledPlugin("com.intellij.java")
    }
}

intellijPlatform {
    pluginConfiguration {
        id = "ru.proofforge.bridge"
        name = "Proof Forge"
        version = project.version.toString()
        vendor {
            name = "Proof Forge"
        }
    }
}

kotlin {
    jvmToolchain(21)
}
