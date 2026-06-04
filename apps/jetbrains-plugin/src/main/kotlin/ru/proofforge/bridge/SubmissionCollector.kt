package ru.proofforge.bridge

import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VfsUtilCore
import com.intellij.openapi.vfs.VirtualFile

class SubmissionCollector(private val project: Project) {
    fun collectProjectFiles(limit: Int = 20): List<Pair<String, String>> {
        val baseDir = project.baseDir ?: return emptyList()
        val result = mutableListOf<Pair<String, String>>()
        collect(baseDir, baseDir, result, limit)
        return result
    }

    private fun collect(root: VirtualFile, current: VirtualFile, result: MutableList<Pair<String, String>>, limit: Int) {
        if (result.size >= limit) return
        if (current.isDirectory) {
            if (current.name in setOf(".git", ".gradle", "build", "node_modules", ".idea")) return
            current.children.forEach { collect(root, it, result, limit) }
            return
        }
        if (current.length > 64_000) return
        val path = VfsUtilCore.getRelativePath(current, root, '/') ?: current.name
        val text = String(current.contentsToByteArray(), Charsets.UTF_8)
        result.add(path to text)
    }
}
