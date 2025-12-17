package dto

type NoteCreate struct {
	Symbol  string `json:"symbol" db:"symbol"`
	Title   string `json:"title" db:"title"`
	Content string `json:"content" db:"content"`
}
