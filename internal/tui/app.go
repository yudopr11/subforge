package tui

import (
	"fmt"
	"path/filepath"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/app/binaries"
	"github.com/yudopr11/subforge/internal/app/config"
	"github.com/yudopr11/subforge/internal/app/export"
	"github.com/yudopr11/subforge/internal/app/models"
	"github.com/yudopr11/subforge/internal/app/pipeline"
	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/views/audiopicker"
	"github.com/yudopr11/subforge/internal/tui/views/langpicker"
	"github.com/yudopr11/subforge/internal/tui/views/modelmgr"
	"github.com/yudopr11/subforge/internal/tui/views/repl"
	"github.com/yudopr11/subforge/internal/tui/views/review"
	"github.com/yudopr11/subforge/internal/tui/views/wizard"
)

type Screen int

const (
	ScreenREPL Screen = iota
	ScreenWizard
	ScreenAudioPicker
	ScreenModelMgr
	ScreenLangPicker
	ScreenReview
)

type TranscribeProgressMsg string
type TranscribeCompleteMsg struct {
	Err error
}

type AppModel struct {
	screen       Screen
	config       *config.AppConfig
	project      *domain.Project
	modelManager *models.Manager

	replView        repl.Model
	wizardView      wizard.Model
	audioPickerView audiopicker.Model
	modelMgrView    modelmgr.Model
	langPickerView  langpicker.Model
	reviewView      review.Model

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

	w, h := 80, 24

	// If there's an existing project in current directory, load it
	var activeProj *domain.Project
	if loaded, err := project.LoadProject("."); err == nil {
		activeProj = loaded
	}

	replM := repl.New(w, h)
	if activeProj != nil {
		replM.SetProject(activeProj)
		replM.AppendLog(fmt.Sprintf("✓ Loaded existing project '%s' from current directory", activeProj.Name))
	}

	return AppModel{
		screen:          startScreen,
		config:          cfg,
		project:         activeProj,
		modelManager:    mgr,
		replView:        replM,
		wizardView:      wizard.New(w, h),
		audioPickerView: audiopicker.New(".", w, h),
		modelMgrView:    modelmgr.New(mgr, w, h),
		langPickerView:  langpicker.New(w, h),
		reviewView:      review.New(activeProj, w, h),
		width:           w,
		height:          h,
	}
}

func (a AppModel) CurrentScreen() Screen {
	return a.screen
}

func (a AppModel) CurrentProject() *domain.Project {
	return a.project
}

func (a AppModel) Config() *config.AppConfig {
	return a.config
}

func (a AppModel) Init() tea.Cmd {
	return a.replView.Init()
}

func (a AppModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		a.width = msg.Width
		a.height = msg.Height
		var cmds []tea.Cmd

		if rm, cmd := a.replView.Update(msg); cmd != nil {
			a.replView = rm.(repl.Model)
			cmds = append(cmds, cmd)
		}
		if wm, cmd := a.wizardView.Update(msg); cmd != nil {
			a.wizardView = wm.(wizard.Model)
			cmds = append(cmds, cmd)
		}
		if rvm, cmd := a.reviewView.Update(msg); cmd != nil {
			a.reviewView = rvm.(review.Model)
			cmds = append(cmds, cmd)
		}
		if mm, cmd := a.modelMgrView.Update(msg); cmd != nil {
			a.modelMgrView = mm.(modelmgr.Model)
			cmds = append(cmds, cmd)
		}
		a.audioPickerView.List.SetSize(a.width, a.height-4)
		a.langPickerView.List.SetSize(a.width, a.height-4)

		return a, tea.Batch(cmds...)

	case TranscribeProgressMsg:
		a.replView.AppendLog(string(msg))
		return a, nil

	case TranscribeCompleteMsg:
		if msg.Err != nil {
			a.replView.AppendLog("[ERROR] Transcription failed: " + msg.Err.Error())
		} else {
			a.replView.SetProject(a.project)
			a.replView.AppendLog(fmt.Sprintf("✓ Transcribed %d captions successfully", len(a.project.Segments)))
		}
		return a, nil

	case repl.ExecuteCommandMsg:
		switch msg.Command {
		case "quit", "exit", "q":
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
				dir := msg.Args[0]
				if loaded, err := project.LoadProject(dir); err == nil {
					a.project = loaded
					a.replView.SetProject(loaded)
					a.replView.AppendLog(fmt.Sprintf("✓ Opened project '%s'", loaded.Name))
				} else {
					a.replView.AppendLog(fmt.Sprintf("[ERROR] Failed to open project at %s: %v", dir, err))
				}
			} else {
				if loaded, err := project.LoadProject("."); err == nil {
					a.project = loaded
					a.replView.SetProject(loaded)
					a.replView.AppendLog(fmt.Sprintf("✓ Opened project '%s' from current directory", loaded.Name))
				} else {
					a.replView.AppendLog("No project.json found in current directory. Use /new to create one.")
				}
			}

		case "projects":
			projects, err := project.ListProjects(".")
			if err != nil || len(projects) == 0 {
				a.replView.AppendLog("No projects found under current working directory.")
			} else {
				a.replView.AppendLog(fmt.Sprintf("Found %d project(s):", len(projects)))
				for _, p := range projects {
					a.replView.AppendLog(fmt.Sprintf("  • %s (%d segments, model: %s, lang: %s)", p.Name, len(p.Segments), p.Model, p.Language))
				}
			}

		case "status":
			if a.project == nil {
				a.replView.AppendLog("No active project loaded.")
			} else {
				a.replView.AppendLog(fmt.Sprintf("Project: %s | Audio: %s | Model: %s | Lang: %s", a.project.Name, a.project.AudioPath, a.project.Model, a.project.Language))
				a.replView.AppendLog(fmt.Sprintf("Transcribe stage: %s (%d segments)", a.project.Stages["transcribe"], len(a.project.Segments)))
				a.replView.AppendLog(fmt.Sprintf("Export stage: %s", a.project.Stages["export"]))
			}

		case "review":
			if a.project != nil {
				a.reviewView = review.New(a.project, a.width, a.height)
				a.screen = ScreenReview
			} else {
				a.replView.AppendLog("[ERROR] No project loaded. Create one with /new first.")
			}

		case "models":
			a.modelMgrView = modelmgr.New(a.modelManager, a.width, a.height)
			a.screen = ScreenModelMgr

		case "language", "lang":
			if len(msg.Args) > 0 {
				lang := strings.ToLower(msg.Args[0])
				a.config.DefaultLanguage = lang
				_ = config.SaveConfig(a.config)
				if a.project != nil {
					a.project.Language = lang
					_ = project.SaveProject(a.project, ".")
				}
				a.replView.AppendLog("✓ Language set to " + lang)
			} else {
				a.langPickerView = langpicker.New(a.width, a.height)
				a.screen = ScreenLangPicker
			}

		case "wizard":
			a.wizardView = wizard.New(a.width, a.height)
			a.screen = ScreenWizard

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
					a.replView.AppendLog(fmt.Sprintf("[ERROR] Model '%s' not downloaded. Run /models to download it.", a.project.Model))
				} else {
					whisperBin, err := binaries.FindBinary("whisper-cli")
					if err != nil {
						a.replView.AppendLog(fmt.Sprintf("[ERROR] whisper-cli not found: %v. Please install or place whisper-cli in PATH or ~/.local/share/subforge/bin", err))
					} else {
						proj := a.project
						return a, func() tea.Msg {
							err := pipeline.RunTranscription(proj, ".", modelPath, whisperBin, func(s string) {
								// Progress callback
							})
							if err == nil {
								_ = project.SaveProject(proj, ".")
							}
							return TranscribeCompleteMsg{Err: err}
						}
					}
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
			switch keyMsg.Type {
			case tea.KeyEsc:
				a.screen = ScreenREPL
				return a, nil
			case tea.KeyEnter:
				if selected := a.modelMgrView.SelectedModel(); selected != nil {
					a.config.DefaultModel = selected.Name
					_ = config.SaveConfig(a.config)
					if a.project != nil {
						a.project.Model = selected.Name
						_ = project.SaveProject(a.project, ".")
					}
					a.replView.AppendLog(fmt.Sprintf("✓ Active model set to '%s'", selected.Name))
					a.screen = ScreenREPL
					return a, nil
				}
			}
		}
		var cmd tea.Cmd
		var updatedModel tea.Model
		updatedModel, cmd = a.modelMgrView.Update(msg)
		a.modelMgrView = updatedModel.(modelmgr.Model)
		return a, cmd

	case ScreenAudioPicker:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			switch keyMsg.Type {
			case tea.KeyEsc:
				a.screen = ScreenREPL
				return a, nil
			case tea.KeyEnter:
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
		a.audioPickerView.List, cmd = a.audioPickerView.List.Update(msg)
		return a, cmd

	case ScreenLangPicker:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			switch keyMsg.Type {
			case tea.KeyEsc:
				a.screen = ScreenREPL
				return a, nil
			case tea.KeyEnter:
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
		a.langPickerView.List, cmd = a.langPickerView.List.Update(msg)
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
		return a.audioPickerView.List.View()
	case ScreenLangPicker:
		return a.langPickerView.List.View()
	default:
		return a.replView.View()
	}
}
