package templates

import (
	"errors"
	"html"
	"strings"
	"testing"
)

// sampleData holds the fields each template's callers send (see README).
var sampleData = map[string]map[string]any{
	"verify_email":    {"username": "an@example.com", "verify_link": "http://localhost:5173/signup-verify?token=t", "expiry_hours": 30},
	"reset_password":  {"username": "an@example.com", "link": "http://localhost:5173/reset-password?token=t", "valid_hours": 1},
	"new_account":     {"username": "an@example.com", "password": "Temp#123", "link": "http://localhost:5173"},
	"test_email":      {"email": "an@example.com"},
	"alert_triggered": {"symbol": "AAPL", "price": 151.2, "conditions": "PRICE > 150", "triggered_at": "2026-10-27 14:30:05 UTC"},
}

func newRenderer(t *testing.T) *Renderer {
	t.Helper()
	r, err := New(map[string]any{"app_name": "Kstock", "project_name": "Kstock", "year": 2026})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return r
}

func TestEveryTemplateRenders(t *testing.T) {
	r := newRenderer(t)
	for _, name := range Names() {
		data, ok := sampleData[name]
		if !ok {
			t.Fatalf("no sample data for template %s", name)
		}
		subject, body, err := r.Render(name, data)
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		if !strings.Contains(subject, "Kstock") {
			t.Errorf("%s: subject %q lacks app name", name, subject)
		}
		for key, v := range data {
			if s, ok := v.(string); ok && !strings.Contains(body, html.EscapeString(s)) {
				t.Errorf("%s: body lacks %s=%q", name, key, s)
			}
		}
		if strings.Contains(subject+body, "<no value>") {
			t.Errorf("%s: rendered a missing key as <no value>", name)
		}
	}
}

func TestMissingKeysRenderEmpty(t *testing.T) {
	r := newRenderer(t)
	for _, name := range Names() {
		subject, body, err := r.Render(name, nil)
		if err != nil {
			t.Fatalf("%s: %v", name, err)
		}
		if strings.Contains(subject+body, "<no value>") {
			t.Errorf("%s: rendered a missing key as <no value>", name)
		}
	}
}

func TestBodyEscapesData(t *testing.T) {
	r := newRenderer(t)
	_, body, err := r.Render("test_email", map[string]any{"email": "<script>alert(1)</script>"})
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(body, "<script>alert(1)") {
		t.Fatal("body contains unescaped user data")
	}
}

func TestRequestDataOverridesDefaults(t *testing.T) {
	r := newRenderer(t)
	subject, _, err := r.Render("test_email", map[string]any{"app_name": "Other", "email": "a@b.c"})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasPrefix(subject, "Other") {
		t.Fatalf("subject = %q, want request app_name", subject)
	}
	if r.Defaults["app_name"] != "Kstock" {
		t.Fatal("Render mutated Defaults")
	}
}

func TestUnknownTemplate(t *testing.T) {
	_, _, err := newRenderer(t).Render("nope", nil)
	if !errors.Is(err, ErrUnknownTemplate) {
		t.Fatalf("err = %v, want ErrUnknownTemplate", err)
	}
}
