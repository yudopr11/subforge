package tui

import (
	"fmt"
	"path/filepath"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/app/binaries"
	"github.com/yudopr11/subforge/internal/app/config"
	"github.com/yudopr11/subforge/internal/app/export"
	"github.com/yudopr11/subforge/internal/app/models"
	"github.com/yudopr11/subforge/internal/app/pipeline"
	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/theme"
	"github.com/yudopr11/subforge/internal/tui/views/audiopicker"
	"github.com/yudopr11/subforge/internal/tui/views/langpicker"
	"github.com/yudopr11/subforge/internal/tui/views/modelmgr"
	"github.com/yudopr11/subforge/internal/tui/views/projectpicker"
	"github.com/yudopr11/subforge/internal/tui/views/repl"
	"github.com/yudopr11/subforge/internal/tui/views/review"
	"github.com/yudopr11/subforge/internal/tui/views/wizard"
)

type Screen int

const (
	ScreenREPL Screen = iota
	ScreenWizard
	ScreenAudioPicker
	ScreenProjectPicker
	ScreenModelMgr
	ScreenLangPicker
	ScreenReview
)

type TranscribeProgressMsg struct {
	Line    string
	NextCmd tea.Cmd
}

type TranscribeCompleteMsg struct {
	Err error
}

type pipelineProgressEvent struct {
	Line string
	Done bool
	Err  error
}

func WaitForPipelineProgress(ch <-chan pipelineProgressEvent) tea.Cmd {
	return func() tea.Msg {
		event, ok := <-ch
		if !ok || event.Done {
			return TranscribeCompleteMsg{Err: event.Err}
		}
		return TranscribeProgressMsg{
			Line:    event.Line,
			NextCmd: WaitForPipelineProgress(ch),
		}
	}
}

type AppModel struct {
	screen       Screen
	config       *config.AppConfig
	project      *domain.Project
	modelManager *models.Manager

	replView          repl.Model
	wizardView        wizard.Model
	audioPickerView   audiopicker.Model
	projectPickerView projectpicker.Model
	modelMgrView      modelmgr.Model
	langPickerView    langpicker.Model
	reviewView        review.Model

	width  int
	height int
}

func NewApp() AppModel {
	cfg, _ := config.LoadConfig()
	mgr := models.NewManager("")

	startScreen := ScreenREPL
	if !cfg.WizardCompleted {
		startScreen = ScreenWizard
	}

	app := AppModel{
		screen:          startScreen,
		config:          cfg,
		modelManager:    mgr,
		replView:          repl.New(80, 24),
		wizardView:        wizard.New(80, 24),
		audioPickerView:   audiopicker.New(".", 80, 24),
		projectPickerView: projectpicker.New(".", 80, 24),
		modelMgrView:      modelmgr.New(mgr, 80, 24),
		langPickerView:    langpicker.New(80, 24),
		width:           80,
		height:          24,
	}

	// Try auto-loading existing project in current directory
	if existing, err := project.LoadProject("."); err == nil {
		app.project = existing
		app.replView.SetProject(existing)
		app.replView.AppendLog(fmt.Sprintf("✓ Loaded existing project: %s (%d segments)", existing.Name, len(existing.Segments)))
	}

	return app
}

func (a AppModel) CurrentScreen() Screen {
	return a.screen
}

func (a AppModel) CurrentProject() *domain.Project {
	return a.project
}

func (a AppModel) Init() tea.Cmd {
	return nil
}

func (a AppModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		a.width = msg.Width
		a.height = msg.Height
		var cmds []tea.Cmd
		var m tea.Model
		m, cmd := a.replView.Update(msg)
		a.replView = m.(repl.Model)
		cmds = append(cmds, cmd)

		m, cmd = a.reviewView.Update(msg)
		a.reviewView = m.(review.Model)
		cmds = append(cmds, cmd)

		m, cmd = a.modelMgrView.Update(msg)
		a.modelMgrView = m.(modelmgr.Model)
		cmds = append(cmds, cmd)

		m, cmd = a.wizardView.Update(msg)
		a.wizardView = m.(wizard.Model)
		cmds = append(cmds, cmd)

		var apModel audiopicker.Model
		apModel, cmd = a.audioPickerView.Update(msg)
		a.audioPickerView = apModel
		cmds = append(cmds, cmd)

		var ppModel projectpicker.Model
		ppModel, cmd = a.projectPickerView.Update(msg)
		a.projectPickerView = ppModel
		cmds = append(cmds, cmd)

		var lpModel langpicker.Model
		lpModel, cmd = a.langPickerView.Update(msg)
		a.langPickerView = lpModel
		cmds = append(cmds, cmd)

		return a, tea.Batch(cmds...)

	case modelmgr.ModelSelectedMsg:
		a.config.DefaultModel = msg.Name
		_ = config.SaveConfig(a.config)
		if a.project != nil {
			a.project.Model = msg.Name
			_ = project.SaveProject(a.project, ".")
		}
		a.replView.AppendLog(fmt.Sprintf("✓ Active model set to '%s'", msg.Name))
		a.screen = ScreenREPL
		return a, nil

	case TranscribeProgressMsg:
		if strings.TrimSpace(msg.Line) != "" {
			a.replView.AppendLog(msg.Line)
		}
		return a, msg.NextCmd

	case TranscribeCompleteMsg:
		if msg.Err != nil {
			a.replView.AppendLog(theme.ErrorStyle.Render("[ERROR] " + msg.Err.Error()))
		} else {
			a.replView.SetProject(a.project)
			a.replView.AppendLog(theme.StatusSuccessStyle.Render(fmt.Sprintf("✓ Transcription completed! Generated %d captions.", len(a.project.Segments))))
			a.replView.AppendLog("ℹ Type /review to edit captions or /export to generate SRT/ASS.")
		}
		return a, nil

	case repl.ExecuteCommandMsg:
		switch msg.Command {
		case "quit", "exit":
			return a, tea.Quit

		case "new":
			if len(msg.Args) > 0 {
				audioPath := msg.Args[0]
				baseName := strings.TrimSuffix(filepath.Base(audioPath), filepath.Ext(audioPath))
				proj := domain.NewProject(baseName, audioPath, a.config.DefaultModel, a.config.DefaultLanguage)
				a.project = proj
				a.replView.SetProject(proj)
				a.replView.AppendLog("▸ Created new project from " + audioPath)
				_ = project.SaveProject(proj, ".")
			} else {
				a.audioPickerView = audiopicker.New(".", a.width, a.height)
				a.screen = ScreenAudioPicker
			}

		case "open":
			if len(msg.Args) > 0 {
				targetDir := msg.Args[0]
				proj, err := project.LoadProject(targetDir)
				if err != nil {
					a.replView.AppendLog(fmt.Sprintf("[ERROR] Failed to load project from '%s': %v", targetDir, err))
				} else {
					a.project = proj
					a.replView.SetProject(proj)
					a.replView.AppendLog(fmt.Sprintf("✓ Opened project '%s' (%d captions)", proj.Name, len(proj.Segments)))
				}
			} else {
				a.projectPickerView = projectpicker.New(".", a.width, a.height)
				a.screen = ScreenProjectPicker
			}

		case "projects":
			a.projectPickerView = projectpicker.New(".", a.width, a.height)
			a.screen = ScreenProjectPicker

		case "status":
			if a.project == nil {
				a.replView.AppendLog("No project loaded. Type /new to create a project.")
			} else {
				a.replView.AppendLog(fmt.Sprintf("Project:   %s", a.project.Name))
				a.replView.AppendLog(fmt.Sprintf("Audio:     %s", a.project.AudioPath))
				a.replView.AppendLog(fmt.Sprintf("Model:     %s", a.project.Model))
				a.replView.AppendLog(fmt.Sprintf("Language:  %s", a.project.Language))
				a.replView.AppendLog(fmt.Sprintf("Captions:  %d segments", len(a.project.Segments)))
				a.replView.AppendLog(fmt.Sprintf("Status:    transcribe: %s | export: %s",
					a.project.Stages["transcribe"], a.project.Stages["export"]))
			}

		case "models":
			a.modelMgrView = modelmgr.New(a.modelManager, a.width, a.height)
			a.screen = ScreenModelMgr

		case "language":
			if len(msg.Args) > 0 {
				code := msg.Args[0]
				a.config.DefaultLanguage = code
				_ = config.SaveConfig(a.config)
				if a.project != nil {
					a.project.Language = code
					_ = project.SaveProject(a.project, ".")
				}
				a.replView.AppendLog(fmt.Sprintf("✓ Language set to %s", code))
			} else {
				a.langPickerView = langpicker.New(a.width, a.height)
				a.screen = ScreenLangPicker
			}

		case "wizard":
			a.wizardView = wizard.New(a.width, a.height)
			a.screen = ScreenWizard

		case "review":
			if a.project != nil {
				if len(a.project.Segments) == 0 {
					a.replView.AppendLog("[ERROR] Project has 0 captions. Run /transcribe first.")
				} else {
					a.reviewView = review.New(a.project, a.width, a.height)
					a.screen = ScreenReview
				}
			} else {
				a.replView.AppendLog("[ERROR] No project loaded. Create one with /new first.")
			}

		case "export":
			if a.project != nil {
				formats := []string{"srt", "ass"}
				if len(msg.Args) > 0 {
					formats = msg.Args
				}
				files, err := export.ExportFiles(a.project, ".", formats)
				if err != nil {
					a.replView.AppendLog("[ERROR] Export failed: " + err.Error())
				} else {
					if a.project.Stages == nil {
						a.project.Stages = make(map[string]domain.StageStatus)
					}
					a.project.Stages["export"] = domain.StatusCompleted
					_ = project.SaveProject(a.project, ".")
					for _, f := range files {
						a.replView.AppendLog("✓ Exported: " + f)
					}
				}
			} else {
				a.replView.AppendLog("[ERROR] No project loaded to export.")
			}

		case "transcribe":
			if a.project != nil {
				a.replView.AppendLog("▸ Starting transcription pipeline...")
				modelPath, exists := a.modelManager.GetModelPath(a.project.Model)
				if !exists {
					a.replView.AppendLog(fmt.Sprintf("[ERROR] Model '%s' not downloaded. Run /models to download it first.", a.project.Model))
				} else {
					proj := a.project
					ch := make(chan pipelineProgressEvent, 50)
					go func() {
						whisperBin, err := binaries.EnsureWhisperBinary(func(curr, tot int64, status string) {
							ch <- pipelineProgressEvent{Line: status}
						})
						if err != nil {
							ch <- pipelineProgressEvent{Done: true, Err: fmt.Errorf("whisper-cli setup failed: %w", err)}
							close(ch)
							return
						}

						ch <- pipelineProgressEvent{Line: "▸ Converting audio & running Whisper..."}
						err = pipeline.RunTranscription(proj, ".", modelPath, whisperBin, func(line string) {
							ch <- pipelineProgressEvent{Line: line}
						})
						if err == nil {
							_ = project.SaveProject(proj, ".")
						}
						ch <- pipelineProgressEvent{Done: true, Err: err}
						close(ch)
					}()
					return a, WaitForPipelineProgress(ch)
				}
			} else {
				a.replView.AppendLog("[ERROR] No project loaded. Use /new to create one.")
			}

		case "help", "?":
			a.replView.AppendLog("SubForge Commands:")
			a.replView.AppendLog("  /new [file]        - Create a new project (or open audio picker)")
			a.replView.AppendLog("  /open [path]       - Open existing project.json")
			a.replView.AppendLog("  /transcribe        - Run local Whisper transcription")
			a.replView.AppendLog("  /review            - Open caption & speaker editor")
			a.replView.AppendLog("  /export [srt|ass]  - Export subtitle files")
			a.replView.AppendLog("  /models            - Whisper GGML model manager")
			a.replView.AppendLog("  /language [code]   - Set audio source language")
			a.replView.AppendLog("  /projects          - List projects in current folder")
			a.replView.AppendLog("  /status            - Show current project details")
			a.replView.AppendLog("  /wizard            - Re-run hardware setup wizard")
			a.replView.AppendLog("  quit, exit         - Exit SubForge")

		default:
			a.replView.AppendLog(fmt.Sprintf("Unknown command: /%s. Type ? or help for available commands.", msg.Command))
		}
		return a, nil
	}

	switch a.screen {
	case ScreenWizard:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			switch keyMsg.Type {
			case tea.KeyEnter:
				a.config.DefaultModel = a.wizardView.RecModel()
				a.config.WizardCompleted = true
				_ = config.SaveConfig(a.config)
				a.replView.AppendLog(fmt.Sprintf("✓ Wizard completed: default model set to %s", a.config.DefaultModel))
				a.screen = ScreenREPL
				return a, nil
			case tea.KeyEsc:
				a.config.WizardCompleted = true
				_ = config.SaveConfig(a.config)
				a.replView.AppendLog("ℹ Setup wizard skipped.")
				a.screen = ScreenREPL
				return a, nil
			}
		}
		var cmd tea.Cmd
		var updatedModel tea.Model
		updatedModel, cmd = a.wizardView.Update(msg)
		a.wizardView = updatedModel.(wizard.Model)
		return a, cmd

	case ScreenReview:
		if keyMsg, ok := msg.(tea.KeyMsg); ok && keyMsg.Type == tea.KeyEsc {
			if !a.reviewView.IsEditing() {
				if a.project != nil {
					_ = project.SaveProject(a.project, ".")
				}
				a.replView.SetProject(a.project)
				a.replView.AppendLog("✓ Returned from caption review. Project saved.")
				a.screen = ScreenREPL
				return a, nil
			}
		}
		var cmd tea.Cmd
		var updatedModel tea.Model
		updatedModel, cmd = a.reviewView.Update(msg)
		a.reviewView = updatedModel.(review.Model)
		return a, cmd

	case ScreenModelMgr:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			if (keyMsg.Type == tea.KeyEsc || keyMsg.String() == "q") && !a.modelMgrView.IsDownloading() {
				a.screen = ScreenREPL
				return a, nil
			}
		}
		var cmd tea.Cmd
		var updatedModel tea.Model
		updatedModel, cmd = a.modelMgrView.Update(msg)
		a.modelMgrView = updatedModel.(modelmgr.Model)
		return a, cmd

	case ScreenAudioPicker:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			if a.audioPickerView.List.FilterState() == list.Unfiltered {
				if keyMsg.Type == tea.KeyEsc || keyMsg.String() == "q" {
					a.screen = ScreenREPL
					return a, nil
				}
			}
			if keyMsg.Type == tea.KeyEnter {
				if item, ok := a.audioPickerView.List.SelectedItem().(audiopicker.AudioFileItem); ok {
					baseName := strings.TrimSuffix(filepath.Base(item.Path), filepath.Ext(item.Path))
					proj := domain.NewProject(baseName, item.Path, a.config.DefaultModel, a.config.DefaultLanguage)
					a.project = proj
					a.replView.SetProject(proj)
					a.replView.AppendLog("▸ Created new project from " + item.Name)
					_ = project.SaveProject(proj, ".")
					a.screen = ScreenREPL
					return a, nil
				}
			}
		}
		var cmd tea.Cmd
		a.audioPickerView, cmd = a.audioPickerView.Update(msg)
		return a, cmd

	case ScreenProjectPicker:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			if a.projectPickerView.List.FilterState() == list.Unfiltered {
				if keyMsg.Type == tea.KeyEsc || keyMsg.String() == "q" {
					a.screen = ScreenREPL
					return a, nil
				}
			}
			if keyMsg.Type == tea.KeyEnter {
				if item, ok := a.projectPickerView.List.SelectedItem().(projectpicker.ProjectItem); ok && item.Project != nil {
					a.project = item.Project
					a.replView.SetProject(item.Project)
					a.replView.AppendLog(fmt.Sprintf("✓ Opened project '%s' (%d captions)", item.Project.Name, len(item.Project.Segments)))
					a.screen = ScreenREPL
					return a, nil
				}
			}
		}
		var cmd tea.Cmd
		a.projectPickerView, cmd = a.projectPickerView.Update(msg)
		return a, cmd

	case ScreenLangPicker:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			if a.langPickerView.List.FilterState() == list.Unfiltered {
				if keyMsg.Type == tea.KeyEsc || keyMsg.String() == "q" {
					a.screen = ScreenREPL
					return a, nil
				}
			}
			if keyMsg.Type == tea.KeyEnter {
				if item, ok := a.langPickerView.List.SelectedItem().(langpicker.LanguageItem); ok {
					a.config.DefaultLanguage = item.Code
					_ = config.SaveConfig(a.config)
					if a.project != nil {
						a.project.Language = item.Code
						_ = project.SaveProject(a.project, ".")
					}
					a.replView.AppendLog(fmt.Sprintf("✓ Language set to %s (%s)", item.Name, item.Code))
					a.screen = ScreenREPL
					return a, nil
				}
			}
		}
		var cmd tea.Cmd
		a.langPickerView, cmd = a.langPickerView.Update(msg)
		return a, cmd

	default:
		var cmd tea.Cmd
		var updatedModel tea.Model
		updatedModel, cmd = a.replView.Update(msg)
		a.replView = updatedModel.(repl.Model)
		return a, cmd
	}
}

func (a AppModel) View() string {
	switch a.screen {
	case ScreenWizard:
		return a.wizardView.View()
	case ScreenReview:
		return a.reviewView.View()
	case ScreenModelMgr:
		return a.modelMgrView.View()
	case ScreenAudioPicker:
		return a.audioPickerView.View()
	case ScreenProjectPicker:
		return a.projectPickerView.View()
	case ScreenLangPicker:
		return a.langPickerView.View()
	default:
		return a.replView.View()
	}
}
