package ru.proofforge.bridge

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.components.JBPanel
import com.intellij.ui.content.ContentFactory
import java.awt.BorderLayout
import javax.swing.JButton
import javax.swing.JLabel
import javax.swing.JScrollPane
import javax.swing.JTextArea
import javax.swing.JTextField

class ProofForgeToolWindowFactory : ToolWindowFactory {
    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val panel = ProofForgePanel(project)
        val content = ContentFactory.getInstance().createContent(panel.component(), null, false)
        toolWindow.contentManager.addContent(content)
    }
}

class ProofForgePanel(private val project: Project) {
    private val output = JTextArea().apply {
        isEditable = false
        lineWrap = true
        text = "Enter user id, load tasks, then submit evidence from the current project."
    }
    private val apiBase = JTextField("http://localhost:8000")
    private val userId = JTextField("")
    private val taskId = JTextField("")
    private val reflection = JTextArea("I solved the task and ran local checks.").apply { lineWrap = true }

    fun component(): JBPanel<JBPanel<*>> {
        val panel = JBPanel<JBPanel<*>>(BorderLayout())
        val form = JBPanel<JBPanel<*>>().apply {
            layout = java.awt.GridLayout(0, 1, 4, 4)
            add(JLabel("API base URL"))
            add(apiBase)
            add(JLabel("Proof Forge user id"))
            add(userId)
            add(JButton("List active tasks").apply {
                addActionListener { listTasks() }
            })
            add(JLabel("Practice task id"))
            add(taskId)
            add(JLabel("Reflection"))
            add(JScrollPane(reflection))
            add(JButton("Submit current project").apply {
                addActionListener { submit() }
            })
        }
        panel.add(form, BorderLayout.NORTH)
        panel.add(JScrollPane(output), BorderLayout.CENTER)
        return panel
    }

    private fun settings() = ProofForgeSettings(apiBaseUrl = apiBase.text.trim(), userId = userId.text.trim())

    private fun listTasks() {
        runCatching {
            ProofForgeApiClient(settings()).listActiveTasks()
        }.onSuccess {
            output.text = it
        }.onFailure {
            output.text = it.message ?: "Failed to load tasks"
        }
    }

    private fun submit() {
        val files = SubmissionCollector(project).collectProjectFiles()
        val filesJson = files.joinToString(",") { (path, content) ->
            """{"path":${json(path)},"content":${json(content)}}"""
        }
        val payload = """
            {
              "practice_task_id": ${json(taskId.text.trim())},
              "user_id": ${json(userId.text.trim())},
              "files": [$filesJson],
              "diff": "",
              "test_output": "",
              "check_command": "",
              "exit_code": null,
              "reflection": ${json(reflection.text)},
              "language": "unknown"
            }
        """.trimIndent()
        runCatching {
            ProofForgeApiClient(settings()).submit(taskId.text.trim(), payload)
        }.onSuccess {
            output.text = it
        }.onFailure {
            output.text = it.message ?: "Failed to submit"
        }
    }

    private fun json(value: String): String {
        return "\"" + value
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n") + "\""
    }
}
