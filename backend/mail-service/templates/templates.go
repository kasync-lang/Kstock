// Package templates owns every email Kstock sends. Callers only name a template
// and pass its data; subject and HTML body are rendered here.
package templates

import (
	"bytes"
	"embed"
	"errors"
	"fmt"
	htmltemplate "html/template"
	"maps"
	"strings"
	texttemplate "text/template"
)

//go:embed html/*.html
var files embed.FS

// ErrUnknownTemplate means the request named a template that does not exist.
// Retrying will not help, so the handler drops the message.
var ErrUnknownTemplate = errors.New("unknown template")

// spec maps a template name to its subject line and body file. Subjects are
// plain text, so they use text/template (no HTML escaping in the header).
var spec = map[string]struct {
	subject string
	file    string
}{
	"verify_email":    {"{{.app_name}} - Xác thực email đăng ký", "verify_email.html"},
	"reset_password":  {"{{.app_name}} - Khôi phục mật khẩu cho {{.username}}", "reset_password.html"},
	"new_account":     {"{{.app_name}} - Tài khoản mới cho {{.username}}", "new_account.html"},
	"test_email":      {"{{.app_name}} - Test email", "test_email.html"},
	"alert_triggered": {"{{.app_name}} - Cảnh báo {{.symbol}} đã kích hoạt", "alert_triggered.html"},
}

type compiled struct {
	subject *texttemplate.Template
	body    *htmltemplate.Template
}

// Renderer renders templates with request data on top of Defaults (app_name,
// support_email, year, ...), so callers only send what is specific to the email.
type Renderer struct {
	Defaults map[string]any
	byName   map[string]compiled
}

// New parses every template up front so a broken one fails at startup, not on
// the first email that needs it.
func New(defaults map[string]any) (*Renderer, error) {
	r := &Renderer{Defaults: defaults, byName: make(map[string]compiled, len(spec))}
	for name, s := range spec {
		subject, err := texttemplate.New(name).Option("missingkey=zero").Parse(s.subject)
		if err != nil {
			return nil, fmt.Errorf("parse subject %s: %w", name, err)
		}
		body, err := htmltemplate.New(s.file).Option("missingkey=zero").ParseFS(files, "html/"+s.file)
		if err != nil {
			return nil, fmt.Errorf("parse body %s: %w", name, err)
		}
		r.byName[name] = compiled{subject: subject, body: body}
	}
	return r, nil
}

// Names returns the registered template names.
func Names() []string {
	names := make([]string, 0, len(spec))
	for name := range spec {
		names = append(names, name)
	}
	return names
}

func (r *Renderer) Render(name string, data map[string]any) (subject, body string, err error) {
	t, ok := r.byName[name]
	if !ok {
		return "", "", fmt.Errorf("%w: %q", ErrUnknownTemplate, name)
	}
	merged := maps.Clone(r.Defaults)
	if merged == nil {
		merged = make(map[string]any, len(data))
	}
	maps.Copy(merged, data)

	var sb, bb bytes.Buffer
	if err := t.subject.Execute(&sb, merged); err != nil {
		return "", "", fmt.Errorf("render subject %s: %w", name, err)
	}
	if err := t.body.Execute(&bb, merged); err != nil {
		return "", "", fmt.Errorf("render body %s: %w", name, err)
	}
	// text/template prints a missing map key as "<no value>" even with
	// missingkey=zero; html/template already renders it as empty.
	return strings.ReplaceAll(sb.String(), "<no value>", ""), bb.String(), nil
}
