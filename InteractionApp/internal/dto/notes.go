package dto

type NoteCreate struct {
	Symbol  string `json:"symbol" db:"symbol"`
	Title   string `json:"title" db:"title"`
	Content string `json:"content" db:"content"`
}
type NotePublic struct {
	ID    string `json:"id" db:"note_id"`
	Title string `json:"title" db:"title"`
}
type NoteDetail struct {
	NotePublic
	Update   string `json:"updated_at" db:"updated_at"`
	Content  string `json:"content" db:"content"`
	Symbol   string `json:"symbol" db:"symbol"`
	CreateAt string `json:"created_at" db:"created_at"`
}
type NoteUpdate struct {
	ID      string  `json:"id" db:"note_id"`
	Title   *string `json:"title" db:"title"`
	Content *string `json:"content" db:"content"`
}
