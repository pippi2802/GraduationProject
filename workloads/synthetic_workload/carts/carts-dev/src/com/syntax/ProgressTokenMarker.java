/*
 * ProgressTokenMarker.java -
 * Copyright (C) 1998, 1999 Slava Pestov
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
 */
package com.syntax;

import javax.swing.text.Segment;

/**
 * C token marker.
 * 
 * @author Slava Pestov
 * @version $Id: ProgressTokenMarker.java,v 1.35 2000/01/29 10:12:43 sp Exp $
 */
public class ProgressTokenMarker extends TokenMarker {
	public ProgressTokenMarker() {
		this(true, false, getKeywords());
		cpp = false;
		javadoc = false;
	}

	public ProgressTokenMarker(boolean cpp, boolean javadoc, KeywordMap keywords) {
		this.cpp = cpp;
		this.javadoc = javadoc;
		this.keywords = keywords;
		cpp = false;
		javadoc = false;
	}

	public byte markTokensImpl(byte token, Segment line, int lineIndex) {
		char[] array = line.array;
		int offset = line.offset;
		lastOffset = offset;
		lastKeyword = offset;
		int length = line.count + offset;
		boolean backslash = false;

		loop: for (int i = offset; i < length; i++) {
			int i1 = (i + 1);

			char c = array[i];
			if (c == '\\') {
				backslash = !backslash;
				continue;
			}

			switch (token) {
			case Token.NULL:
				switch (c) {
				case '#':
					if (backslash)
						backslash = false;
					else if (cpp) {
						if (doKeyword(line, i, c))
							break;
						addToken(i - lastOffset, token);
						addToken(length - i, Token.KEYWORD2);
						lastOffset = lastKeyword = length;
						break loop;
					}
					break;
				case '"':
					doKeyword(line, i, c);
					if (backslash)
						backslash = false;
					else {
						addToken(i - lastOffset, token);
						token = Token.LITERAL1;
						lastOffset = lastKeyword = i;
					}
					break;
				case '\'':
					doKeyword(line, i, c);
					if (backslash)
						backslash = false;
					else {
						addToken(i - lastOffset, token);
						token = Token.LITERAL2;
						lastOffset = lastKeyword = i;
					}
					break;
				case ':':
					if (lastKeyword == offset) {
						if (doKeyword(line, i, c))
							break;
						backslash = false;
						addToken(i1 - lastOffset, Token.LABEL);
						lastOffset = lastKeyword = i1;
					} else if (doKeyword(line, i, c))
						break;
					break;
				case '/':
					backslash = false;
					doKeyword(line, i, c);
					if (length - i > 1) {
						switch (array[i1]) {
						case '*':
							addToken(i - lastOffset, token);
							lastOffset = lastKeyword = i;
							if (javadoc && length - i > 2
									&& array[i + 2] == '*')
								token = Token.COMMENT2;
							else
								token = Token.COMMENT1;
							break;
						case '/':
							addToken(i - lastOffset, token);
							addToken(length - i, Token.COMMENT1);
							lastOffset = lastKeyword = length;
							break loop;
						}
					}
					break;
				default:
					backslash = false;
					if (!Character.isLetterOrDigit(c)
							&& (c != '_' && c != '-' && c != '{' && c != '}'
									&& c != '&' && c != '<' && c != '>'
									&& c != '@' && c != '+' && c != '='
									&& c != '[' && c != ']' && c != '?'
									&& c != '^' && c != '~'))

						doKeyword(line, i, c);
					break;
				}
				break;
			case Token.COMMENT1:
			case Token.COMMENT2:
				backslash = false;
				if (c == '*' && length - i > 1) {
					if (array[i1] == '/') {
						i++;
						addToken((i + 1) - lastOffset, token);
						token = Token.NULL;
						lastOffset = lastKeyword = i + 1;
					}
				}
				break;
			case Token.LITERAL1:
				if (backslash)
					backslash = false;
				else if (c == '"') {
					addToken(i1 - lastOffset, token);
					token = Token.NULL;
					lastOffset = lastKeyword = i1;
				}
				break;
			case Token.LITERAL2:
				if (backslash)
					backslash = false;
				else if (c == '\'') {
					addToken(i1 - lastOffset, Token.LITERAL1);
					token = Token.NULL;
					lastOffset = lastKeyword = i1;
				}
				break;
			default:
				throw new InternalError("Invalid state: " + token);
			}
		}

		if (token == Token.NULL)
			doKeyword(line, length, '\0');

		switch (token) {
		case Token.LITERAL1:
		case Token.LITERAL2:
			addToken(length - lastOffset, Token.INVALID);
			token = Token.NULL;
			break;
		case Token.KEYWORD2:
			addToken(length - lastOffset, token);
			if (!backslash)
				token = Token.NULL;
		default:
			addToken(length - lastOffset, token);
			break;
		}

		return token;
	}

	public static KeywordMap getKeywords() {
		if (progKeywords == null) {
			progKeywords = new KeywordMap(true);

			progKeywords.add("comment1", Token.COMMENT1);
			progKeywords.add("comment2", Token.COMMENT2);

			progKeywords.add("key1", Token.KEYWORD1); // blue
			progKeywords.add("key2", Token.KEYWORD2);// purple
			progKeywords.add("key3", Token.KEYWORD3);// red

			progKeywords.add("lit1", Token.LITERAL1);// light blue
			progKeywords.add("lit2", Token.LITERAL2);// red

			progKeywords.add("label", Token.LABEL);// burgundy
			progKeywords.add("operator", Token.OPERATOR);// black
			progKeywords.add("invalid", Token.INVALID);// red

			progKeywords.add("ABORT", Token.KEYWORD1);
			progKeywords.add("ABSOLUTE", Token.KEYWORD1);
			progKeywords.add("ACCELERATOR", Token.KEYWORD1);
			progKeywords.add("ACCUMULATE", Token.KEYWORD1);
			progKeywords.add("ACROSS", Token.KEYWORD1);
			progKeywords.add("ACTIVE-WINDOW", Token.KEYWORD1);
			progKeywords.add("ADD", Token.KEYWORD1);
			progKeywords.add("ADD-BUFFER", Token.KEYWORD1);
			progKeywords.add("ADD-CALC-COLUMN", Token.KEYWORD1);
			progKeywords.add("ADD-COLUMNS-FROM", Token.KEYWORD1);
			progKeywords.add("ADD-EVENTS-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("ADD-FIELDS-FROM", Token.KEYWORD1);
			progKeywords.add("ADD-FIRST", Token.KEYWORD1);
			progKeywords.add("ADD-INDEX-FIELD", Token.KEYWORD1);
			progKeywords.add("ADD-LAST", Token.KEYWORD1);
			progKeywords.add("ADD-LIKE-COLUMN", Token.KEYWORD1);
			progKeywords.add("ADD-LIKE-FIELD", Token.KEYWORD1);
			progKeywords.add("ADD-LIKE-INDEX", Token.KEYWORD1);
			progKeywords.add("ADD-NEW-FIELD", Token.KEYWORD1);
			progKeywords.add("ADD-NEW-INDEX", Token.KEYWORD1);
			progKeywords.add("ADD-SUPER-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("ADM-DATA", Token.KEYWORD1);
			progKeywords.add("ADVISE", Token.KEYWORD1);
			progKeywords.add("ALERT-BOX", Token.KEYWORD1);
			progKeywords.add("ALIAS", Token.KEYWORD1);
			progKeywords.add("ALL", Token.KEYWORD1);
			progKeywords.add("ALLOW-COLUMN-SEARCHING", Token.KEYWORD1);
			progKeywords.add("ALLOW-REPLICATION", Token.KEYWORD1);
			progKeywords.add("ALTER", Token.KEYWORD1);
			progKeywords.add("ALTERNATE-KEY", Token.KEYWORD1);
			progKeywords.add("ALWAYS-ON-TOP", Token.KEYWORD1);
			progKeywords.add("AMBIGUOUS", Token.KEYWORD1);
			progKeywords.add("AND", Token.KEYWORD1);
			progKeywords.add("ANSI-ONLY", Token.KEYWORD1);
			progKeywords.add("ANY", Token.KEYWORD1);
			progKeywords.add("ANY-KEY", Token.KEYWORD1);
			progKeywords.add("ANY-PRINTABLE", Token.KEYWORD1);
			progKeywords.add("ANYWHERE", Token.KEYWORD1);
			progKeywords.add("APPEND", Token.KEYWORD1);
			progKeywords.add("APPEND-CHILD", Token.KEYWORD1);
			progKeywords.add("APPEND-LINE", Token.KEYWORD1);
			progKeywords.add("APPL-ALERT-BOXES", Token.KEYWORD1);
			progKeywords.add("APPLICATION", Token.KEYWORD1);
			progKeywords.add("APPLY", Token.KEYWORD1);
			progKeywords.add("APPSERVER-INFO", Token.KEYWORD1);
			progKeywords.add("APPSERVER-PASSWORD", Token.KEYWORD1);
			progKeywords.add("APPSERVER-USERID", Token.KEYWORD1);
			progKeywords.add("ARRAY-MESSAGE", Token.KEYWORD1);
			progKeywords.add("AS", Token.KEYWORD1);
			progKeywords.add("AS-CURSOR", Token.KEYWORD1);
			progKeywords.add("ASCENDING", Token.KEYWORD1);
			progKeywords.add("ASK-OVERWRITE", Token.KEYWORD1);
			progKeywords.add("ASSIGN", Token.KEYWORD1);
			progKeywords.add("ASYNC-REQUEST-COUNT", Token.KEYWORD1);
			progKeywords.add("ASYNCHRONOUS", Token.KEYWORD1);
			progKeywords.add("AT", Token.KEYWORD1);
			progKeywords.add("ATTACHMENT", Token.KEYWORD1);
			progKeywords.add("ATTR-SPACE", Token.KEYWORD1);
			progKeywords.add("ATTRIBUTE-NAMES", Token.KEYWORD1);
			progKeywords.add("ATTRIBUTE-TYPE", Token.KEYWORD1);
			progKeywords.add("AUTHORIZATION", Token.KEYWORD1);
			progKeywords.add("AUTO-COMPLETION", Token.KEYWORD1);
			progKeywords.add("AUTO-DELETE-XML", Token.KEYWORD1);
			progKeywords.add("AUTO-END-KEY", Token.KEYWORD1);
			progKeywords.add("AUTO-ENDKEY", Token.KEYWORD1);
			progKeywords.add("AUTO-GO", Token.KEYWORD1);
			progKeywords.add("AUTO-INDENT", Token.KEYWORD1);
			progKeywords.add("AUTO-RESIZE", Token.KEYWORD1);
			progKeywords.add("AUTO-RETURN", Token.KEYWORD1);
			progKeywords.add("AUTO-VALIDATE", Token.KEYWORD1);
			progKeywords.add("AUTO-ZAP", Token.KEYWORD1);
			progKeywords.add("AUTOMATIC", Token.KEYWORD1);
			progKeywords.add("AVAILABLE", Token.KEYWORD1);
			progKeywords.add("AVAILABLE-FORMATS", Token.KEYWORD1);
			progKeywords.add("AVERAGE", Token.KEYWORD1);
			progKeywords.add("AVG", Token.KEYWORD1);
			progKeywords.add("BACKGROUND", Token.KEYWORD1);
			progKeywords.add("BACK-TAB", Token.KEYWORD1);
			progKeywords.add("BACKSPACE", Token.KEYWORD1);
			progKeywords.add("BACKWARDS", Token.KEYWORD1);
			progKeywords.add("BASE-KEY", Token.KEYWORD1);
			progKeywords.add("BATCH-MODE", Token.KEYWORD1);
			progKeywords.add("BEFORE-HIDE", Token.KEYWORD1);
			progKeywords.add("BEGINS", Token.KEYWORD1);
			progKeywords.add("BELL", Token.KEYWORD1);
			progKeywords.add("BETWEEN", Token.KEYWORD1);
			progKeywords.add("BGCOLOR", Token.KEYWORD1);
			progKeywords.add("BIG-ENDIAN", Token.KEYWORD1);
			progKeywords.add("BINARY", Token.KEYWORD1);
			progKeywords.add("BIND-WHERE", Token.KEYWORD1);
			progKeywords.add("BLANK", Token.KEYWORD1);
			progKeywords.add("BLOCK", Token.KEYWORD1);
			progKeywords.add("BLOCK-ITERATION-DISPLAY", Token.KEYWORD1);
			progKeywords.add("BORDER-BOTTOM", Token.KEYWORD1);
			progKeywords.add("BORDER-BOTTOM-CHARS", Token.KEYWORD1);
			progKeywords.add("BORDER-BOTTOM-PIXELS", Token.KEYWORD1);
			progKeywords.add("BORDER-LEFT", Token.KEYWORD1);
			progKeywords.add("BORDER-LEFT-CHARS", Token.KEYWORD1);
			progKeywords.add("BORDER-LEFT-PIXELS", Token.KEYWORD1);
			progKeywords.add("BORDER-RIGHT", Token.KEYWORD1);
			progKeywords.add("BORDER-RIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("BORDER-RIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("BORDER-TOP", Token.KEYWORD1);
			progKeywords.add("BORDER-TOP-CHARS", Token.KEYWORD1);
			progKeywords.add("BORDER-TOP-PIXELS", Token.KEYWORD1);
			progKeywords.add("BOTH", Token.KEYWORD1);
			progKeywords.add("BOTTOM", Token.KEYWORD1);
			progKeywords.add("BOTTOM-COLUMN", Token.KEYWORD1);
			progKeywords.add("BOX", Token.KEYWORD1);
			progKeywords.add("BOX-SELECTABLE", Token.KEYWORD1);
			progKeywords.add("BREAK", Token.KEYWORD1);
			progKeywords.add("BREAK-LINE", Token.KEYWORD1);
			progKeywords.add("BROWSE", Token.KEYWORD1);
			progKeywords.add("BROWSE-COLUMN-DATA-TYPES", Token.KEYWORD1);
			progKeywords.add("BROWSE-COLUMN-FORMATS", Token.KEYWORD1);
			progKeywords.add("BROWSE-COLUMN-LABELS", Token.KEYWORD1);
			progKeywords.add("BROWSE-HEADER", Token.KEYWORD1);
			progKeywords.add("BTOS", Token.KEYWORD1);
			progKeywords.add("BUFFER", Token.KEYWORD1);
			progKeywords.add("BUFFER-CHARS", Token.KEYWORD1);
			progKeywords.add("BUFFER-COMPARE", Token.KEYWORD1);
			progKeywords.add("BUFFER-COPY", Token.KEYWORD1);
			progKeywords.add("BUFFER-CREATE", Token.KEYWORD1);
			progKeywords.add("BUFFER-DELETE", Token.KEYWORD1);
			progKeywords.add("BUFFER-FIELD", Token.KEYWORD1);
			progKeywords.add("BUFFER-HANDLE", Token.KEYWORD1);
			progKeywords.add("BUFFER-LINES", Token.KEYWORD1);
			progKeywords.add("BUFFER-NAME", Token.KEYWORD1);
			progKeywords.add("BUFFER-RELEASE", Token.KEYWORD1);
			progKeywords.add("BUFFER-VALUE", Token.KEYWORD1);
			progKeywords.add("BUTTONS", Token.KEYWORD1);
			progKeywords.add("BY", Token.KEYWORD1);
			progKeywords.add("BY-POINTER", Token.KEYWORD1);
			progKeywords.add("BY-VARIANT-POINTER", Token.KEYWORD1);
			progKeywords.add("BYTE", Token.KEYWORD1);
			progKeywords.add("BYTES-READ", Token.KEYWORD1);
			progKeywords.add("BYTES-WRITTEN", Token.KEYWORD1);
			progKeywords.add("CACHE", Token.KEYWORD1);
			progKeywords.add("CACHE-SIZE", Token.KEYWORD1);
			progKeywords.add("CALL", Token.KEYWORD1);
			progKeywords.add("CAN-CREATE", Token.KEYWORD1);
			progKeywords.add("CAN-DELETE", Token.KEYWORD1);
			progKeywords.add("CAN-DO", Token.KEYWORD1);
			progKeywords.add("CAN-FIND", Token.KEYWORD1);
			progKeywords.add("CAN-QUERY", Token.KEYWORD1);
			progKeywords.add("CAN-READ", Token.KEYWORD1);
			progKeywords.add("CAN-SET", Token.KEYWORD1);
			progKeywords.add("CAN-WRITE", Token.KEYWORD1);
			progKeywords.add("CANCEL-BREAK", Token.KEYWORD1);
			progKeywords.add("CANCEL-BUTTON", Token.KEYWORD1);
			progKeywords.add("CANCEL-PICK", Token.KEYWORD1);
			progKeywords.add("CANCEL-REQUESTS", Token.KEYWORD1);
			progKeywords.add("CANCELLED", Token.KEYWORD1);
			progKeywords.add("CAPS", Token.KEYWORD1);
			progKeywords.add("CAREFUL-PAINT", Token.KEYWORD1);
			progKeywords.add("CASE", Token.KEYWORD1);
			progKeywords.add("CASE-SENSITIVE", Token.KEYWORD1);
			progKeywords.add("CDECL", Token.KEYWORD1);
			progKeywords.add("CENTERED", Token.KEYWORD1);
			progKeywords.add("CHAINED", Token.KEYWORD1);
			progKeywords.add("CHARACTER", Token.KEYWORD1);
			progKeywords.add("CHARACTER_LENGTH", Token.KEYWORD1);
			progKeywords.add("CHARSET", Token.KEYWORD1);
			progKeywords.add("CHECK", Token.KEYWORD1);
			progKeywords.add("CHECKED", Token.KEYWORD1);
			progKeywords.add("CHILD-NUM", Token.KEYWORD1);
			progKeywords.add("CHOICES", Token.KEYWORD1);
			progKeywords.add("CHOOSE", Token.KEYWORD1);
			progKeywords.add("CHR", Token.KEYWORD1);
			progKeywords.add("CLEAR", Token.KEYWORD1);
			progKeywords.add("CLEAR-SELECTION", Token.KEYWORD1);
			progKeywords.add("CLIENT-CONNECTION-ID", Token.KEYWORD1);
			progKeywords.add("CLIENT-TYPE", Token.KEYWORD1);
			progKeywords.add("CLIPBOARD", Token.KEYWORD1);
			progKeywords.add("CLONE-NODE", Token.KEYWORD1);
			progKeywords.add("CLOSE", Token.KEYWORD1);
			progKeywords.add("CODE", Token.KEYWORD1);
			progKeywords.add("CODEBASE-LOCATOR", Token.KEYWORD1);
			progKeywords.add("CODEPAGE", Token.KEYWORD1);
			progKeywords.add("CODEPAGE-CONVERT", Token.KEYWORD1);
			progKeywords.add("COL", Token.KEYWORD1);
			progKeywords.add("COL-OF", Token.KEYWORD1);
			progKeywords.add("COLLATE", Token.KEYWORD1);
			progKeywords.add("COLON", Token.KEYWORD1);
			progKeywords.add("COLON-ALIGNED", Token.KEYWORD1);
			progKeywords.add("COLOR", Token.KEYWORD1);
			progKeywords.add("COLOR-TABLE", Token.KEYWORD1);
			progKeywords.add("COLUMNS", Token.KEYWORD1);
			progKeywords.add("COLUMN-BGCOLOR", Token.KEYWORD1);
			progKeywords.add("COLUMN-DCOLOR", Token.KEYWORD1);
			progKeywords.add("COLUMN-FGCOLOR", Token.KEYWORD1);
			progKeywords.add("COLUMN-FONT", Token.KEYWORD1);
			progKeywords.add("COLUMN-LABEL", Token.KEYWORD1);
			progKeywords.add("COLUMN-LABEL-BGCOLOR", Token.KEYWORD1);
			progKeywords.add("COLUMN-LABEL-DCOLOR", Token.KEYWORD1);
			progKeywords.add("COLUMN-LABEL-FGCOLOR", Token.KEYWORD1);
			progKeywords.add("COLUMN-LABEL-FONT", Token.KEYWORD1);
			progKeywords.add("COLUMN-LABEL-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("COLUMN-LABEL-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("COLUMN-MOVABLE", Token.KEYWORD1);
			progKeywords.add("COLUMN-OF", Token.KEYWORD1);
			progKeywords.add("COLUMN-PFCOLOR", Token.KEYWORD1);
			progKeywords.add("COLUMN-READ-ONLY", Token.KEYWORD1);
			progKeywords.add("COLUMN-RESIZABLE", Token.KEYWORD1);
			progKeywords.add("COLUMN-SCROLLING", Token.KEYWORD1);
			progKeywords.add("COM-HANDLE", Token.KEYWORD1);
			progKeywords.add("COM-SELF", Token.KEYWORD1);
			progKeywords.add("COMBO-BOX", Token.KEYWORD1);
			progKeywords.add("COMMAND", Token.KEYWORD1);
			progKeywords.add("COMPARES", Token.KEYWORD1);
			progKeywords.add("COMPILE", Token.KEYWORD1);
			progKeywords.add("COMPILER", Token.KEYWORD1);
			progKeywords.add("COMPLETE", Token.KEYWORD1);
			progKeywords.add("COMPONENT-HANDLE", Token.KEYWORD1);
			progKeywords.add("COMPONENT-SELF", Token.KEYWORD1);
			progKeywords.add("CONFIG-NAME", Token.KEYWORD1);
			progKeywords.add("CONNECT", Token.KEYWORD1);
			progKeywords.add("CONNECTED", Token.KEYWORD1);
			progKeywords.add("CONSTRAINED", Token.KEYWORD1);
			progKeywords.add("CONTAINER-EVENT", Token.KEYWORD1);
			progKeywords.add("CONTAINS", Token.KEYWORD1);
			progKeywords.add("CONTENTS", Token.KEYWORD1);
			progKeywords.add("CONTEXT", Token.KEYWORD1);
			progKeywords.add("CONTEXT-HELP", Token.KEYWORD1);
			progKeywords.add("CONTEXT-HELP-FILE", Token.KEYWORD1);
			progKeywords.add("CONTEXT-HELP-ID", Token.KEYWORD1);
			progKeywords.add("CONTEXT-POPUP", Token.KEYWORD1);
			progKeywords.add("CONTROL", Token.KEYWORD1);
			progKeywords.add("CONTROL-BOX", Token.KEYWORD1);
			progKeywords.add("CONTROL-CONTAINER", Token.KEYWORD1);
			progKeywords.add("CONTROL-FRAME", Token.KEYWORD1);
			progKeywords.add("CONVERT", Token.KEYWORD1);
			progKeywords.add("CONVERT-3D-COLORS", Token.KEYWORD1);
			progKeywords.add("CONVERT-TO-OFFSET", Token.KEYWORD1);
			progKeywords.add("COPY", Token.KEYWORD1);
			progKeywords.add("COUNT", Token.KEYWORD1);
			progKeywords.add("COUNT-OF", Token.KEYWORD1);
			progKeywords.add("COVERAGE", Token.KEYWORD1);
			progKeywords.add("CPCASE", Token.KEYWORD1);
			progKeywords.add("CPCOLL", Token.KEYWORD1);
			progKeywords.add("CPINTERNAL", Token.KEYWORD1);
			progKeywords.add("CPLOG", Token.KEYWORD1);
			progKeywords.add("CPPRINT", Token.KEYWORD1);
			progKeywords.add("CPRCODEIN", Token.KEYWORD1);
			progKeywords.add("CPRCODEOUT", Token.KEYWORD1);
			progKeywords.add("CPSTREAM", Token.KEYWORD1);
			progKeywords.add("CPTERM", Token.KEYWORD1);
			progKeywords.add("CRC-VALUE", Token.KEYWORD1);
			progKeywords.add("CREATE", Token.KEYWORD1);
			progKeywords.add("CREATE-LIKE", Token.KEYWORD1);
			progKeywords.add("CREATE-NODE", Token.KEYWORD1);
			progKeywords.add("CREATE-NODE-NAMESPACE", Token.KEYWORD1);
			progKeywords.add("CREATE-ON-ADD", Token.KEYWORD1);
			progKeywords.add("CREATE-RESULT-LIST-ENTRY", Token.KEYWORD1);
			progKeywords.add("CREATE-TEST-FILE", Token.KEYWORD1);
			progKeywords.add("CTOS", Token.KEYWORD1);
			progKeywords.add("CURRENT", Token.KEYWORD1);
			progKeywords.add("CURRENT-CHANGED", Token.KEYWORD1);
			progKeywords.add("CURRENT-COLUMN", Token.KEYWORD1);
			progKeywords.add("CURRENT-ENVIRONMENT", Token.KEYWORD1);
			progKeywords.add("CURRENT-ITERATION", Token.KEYWORD1);
			progKeywords.add("CURRENT-LANGUAGE", Token.KEYWORD1);
			progKeywords.add("CURRENT-RESULT-ROW", Token.KEYWORD1);
			progKeywords.add("CURRENT-ROW-MODIFIED", Token.KEYWORD1);
			progKeywords.add("CURRENT-VALUE", Token.KEYWORD1);
			progKeywords.add("CURRENT-WINDOW", Token.KEYWORD1);
			progKeywords.add("CURRENT_DATE", Token.KEYWORD1);
			progKeywords.add("CURSOR", Token.KEYWORD1);
			progKeywords.add("CURSOR-CHAR", Token.KEYWORD1);
			progKeywords.add("CURSOR-DOWN", Token.KEYWORD1);
			progKeywords.add("CURSOR-LEFT", Token.KEYWORD1);
			progKeywords.add("CURSOR-LINE", Token.KEYWORD1);
			progKeywords.add("CURSOR-OFFSET", Token.KEYWORD1);
			progKeywords.add("CURSOR-RIGHT", Token.KEYWORD1);
			progKeywords.add("CURSOR-UP", Token.KEYWORD1);
			progKeywords.add("CUT", Token.KEYWORD1);
			progKeywords.add("DATA-BIND", Token.KEYWORD1);
			progKeywords.add("DATA-ENTRY-RETURN", Token.KEYWORD1);
			progKeywords.add("DATA-REFRESH-LINE", Token.KEYWORD1);
			progKeywords.add("DATA-REFRESH-PAGE", Token.KEYWORD1);
			progKeywords.add("DATA-TYPE", Token.KEYWORD1);
			progKeywords.add("DATABASE", Token.KEYWORD1);
			progKeywords.add("DATASERVERS", Token.KEYWORD1);
			progKeywords.add("DATE", Token.KEYWORD1);
			progKeywords.add("DATE-FORMAT", Token.KEYWORD1);
			progKeywords.add("DAY", Token.KEYWORD1);
			progKeywords.add("DB-REFERENCES", Token.KEYWORD1);
			progKeywords.add("DBCODEPAGE", Token.KEYWORD1);
			progKeywords.add("DBCOLLATION", Token.KEYWORD1);
			progKeywords.add("DBNAME", Token.KEYWORD1);
			progKeywords.add("DBPARAM", Token.KEYWORD1);
			progKeywords.add("DBRESTRICTIONS", Token.KEYWORD1);
			progKeywords.add("DBTASKID", Token.KEYWORD1);
			progKeywords.add("DBTYPE", Token.KEYWORD1);
			progKeywords.add("DBVERSION", Token.KEYWORD1);
			progKeywords.add("DCOLOR", Token.KEYWORD1);
			progKeywords.add("DDE", Token.KEYWORD1);
			progKeywords.add("DDE-ERROR", Token.KEYWORD1);
			progKeywords.add("DDE-ID", Token.KEYWORD1);
			progKeywords.add("DDE-ITEM", Token.KEYWORD1);
			progKeywords.add("DDE-NAME", Token.KEYWORD1);
			progKeywords.add("DDE-NOTIFY", Token.KEYWORD1);
			progKeywords.add("DDE-TOPIC", Token.KEYWORD1);
			progKeywords.add("DEBLANK", Token.KEYWORD1);
			progKeywords.add("DEBUG", Token.KEYWORD1);
			progKeywords.add("DEBUG-ALERT", Token.KEYWORD1);
			progKeywords.add("DEBUG-LIST", Token.KEYWORD1);
			progKeywords.add("DEBUGGER", Token.KEYWORD1);
			progKeywords.add("DECIMAL", Token.KEYWORD1);
			progKeywords.add("DECIMALS", Token.KEYWORD1);
			progKeywords.add("DECLARE", Token.KEYWORD1);
			progKeywords.add("DEFINE", Token.KEYWORD1);
			progKeywords.add("DEFAULT", Token.KEYWORD1);
			progKeywords.add("DEFAULT-ACTION", Token.KEYWORD1);
			progKeywords.add("DEFAULT-BUFFER-HANDLE", Token.KEYWORD1);
			progKeywords.add("DEFAULT-BUTTON", Token.KEYWORD1);
			progKeywords.add("DEFAULT-COMMIT", Token.KEYWORD1);
			progKeywords.add("DEFAULT-EXTENSION", Token.KEYWORD1);
			progKeywords.add("DEFAULT-NOXLATE", Token.KEYWORD1);
			progKeywords.add("DEFAULT-POP-UP", Token.KEYWORD1);
			progKeywords.add("DEFAULT-WINDOW", Token.KEYWORD1);
			progKeywords.add("DEFER-LOB-FETCH", Token.KEYWORD1);
			progKeywords.add("DEFINED", Token.KEYWORD1);
			progKeywords.add("DEL", Token.KEYWORD1);
			progKeywords.add("DELETE", Token.KEYWORD1);
			progKeywords.add("DELETE-CHAR", Token.KEYWORD1);
			progKeywords.add("DELETE-CHARACTER", Token.KEYWORD1);
			progKeywords.add("DELETE-COLUMN", Token.KEYWORD1);
			progKeywords.add("DELETE-CURRENT-ROW", Token.KEYWORD1);
			progKeywords.add("DELETE-END-LINE", Token.KEYWORD1);
			progKeywords.add("DELETE-FIELD", Token.KEYWORD1);
			progKeywords.add("DELETE-LINE", Token.KEYWORD1);
			progKeywords.add("DELETE-NODE", Token.KEYWORD1);
			progKeywords.add("DELETE-RESULT-LIST-ENTRY", Token.KEYWORD1);
			progKeywords.add("DELETE-SELECTED-ROW", Token.KEYWORD1);
			progKeywords.add("DELETE-SELECTED-ROWS", Token.KEYWORD1);
			progKeywords.add("DELETE-WORD", Token.KEYWORD1);
			progKeywords.add("DELIMITER", Token.KEYWORD1);
			progKeywords.add("DESCENDING", Token.KEYWORD1);
			progKeywords.add("DESCRIPTION", Token.KEYWORD1);
			progKeywords.add("DESELECT", Token.KEYWORD1);
			progKeywords.add("DESELECT-EXTEND", Token.KEYWORD1);
			progKeywords.add("DESELECT-FOCUSED-ROW", Token.KEYWORD1);
			progKeywords.add("DESELECT-ROWS", Token.KEYWORD1);
			progKeywords.add("DESELECT-SELECTED-ROW", Token.KEYWORD1);
			progKeywords.add("DESELECTION", Token.KEYWORD1);
			progKeywords.add("DESELECTION-EXTEND", Token.KEYWORD1);
			progKeywords.add("DETACH", Token.KEYWORD1);
			progKeywords.add("DIALOG-BOX", Token.KEYWORD1);
			progKeywords.add("DIALOG-HELP", Token.KEYWORD1);
			progKeywords.add("DICTIONARY", Token.KEYWORD1);
			progKeywords.add("DIR", Token.KEYWORD1);
			progKeywords.add("DIRECTORY", Token.KEYWORD1);
			progKeywords.add("DISABLE", Token.KEYWORD1);
			progKeywords.add("DISABLE-AUTO-ZAP", Token.KEYWORD1);
			progKeywords.add("DISABLE-CONNECTIONS", Token.KEYWORD1);
			progKeywords.add("DISABLE-DUMP-TRIGGERS", Token.KEYWORD1);
			progKeywords.add("DISABLE-LOAD-TRIGGERS", Token.KEYWORD1);
			progKeywords.add("DISABLED", Token.KEYWORD1);
			progKeywords.add("DISCONNECT", Token.KEYWORD1);
			progKeywords.add("DISMISS-MENU", Token.KEYWORD1);
			progKeywords.add("DISPLAY", Token.KEYWORD1);
			progKeywords.add("DISPLAY-MESSAGE", Token.KEYWORD1);
			progKeywords.add("DISPLAY-TYPE", Token.KEYWORD1);
			progKeywords.add("DISTINCT", Token.KEYWORD1);
			progKeywords.add("DO", Token.KEYWORD1);
			progKeywords.add("DOS", Token.KEYWORD1);
			progKeywords.add("DOS-END", Token.KEYWORD1);
			progKeywords.add("DOUBLE", Token.KEYWORD1);
			progKeywords.add("DOWN", Token.KEYWORD1);
			progKeywords.add("DRAG-ENABLED", Token.KEYWORD1);
			progKeywords.add("DROP", Token.KEYWORD1);
			progKeywords.add("DROP-DOWN", Token.KEYWORD1);
			progKeywords.add("DROP-DOWN-LIST", Token.KEYWORD1);
			progKeywords.add("DROP-FILE-NOTIFY", Token.KEYWORD1);
			progKeywords.add("DROP-TARGET", Token.KEYWORD1);
			progKeywords.add("DUMP", Token.KEYWORD1);
			progKeywords.add("DYNAMIC", Token.KEYWORD1);
			progKeywords.add("DYNAMIC-FUNCTION", Token.KEYWORD1);
			progKeywords.add("EACH", Token.KEYWORD1);
			progKeywords.add("ECHO", Token.KEYWORD1);
			progKeywords.add("EDGE", Token.KEYWORD1);
			progKeywords.add("EDGE-CHARS", Token.KEYWORD1);
			progKeywords.add("EDGE-PIXELS", Token.KEYWORD1);
			progKeywords.add("EDIT-CAN-PASTE", Token.KEYWORD1);
			progKeywords.add("EDIT-CAN-UNDO", Token.KEYWORD1);
			progKeywords.add("EDIT-CLEAR", Token.KEYWORD1);
			progKeywords.add("EDIT-COPY", Token.KEYWORD1);
			progKeywords.add("EDIT-CUT", Token.KEYWORD1);
			progKeywords.add("EDIT-PASTE", Token.KEYWORD1);
			progKeywords.add("EDIT-UNDO", Token.KEYWORD1);
			progKeywords.add("EDITING", Token.KEYWORD1);
			progKeywords.add("EDITOR", Token.KEYWORD1);
			progKeywords.add("EDITOR-BACKTAB", Token.KEYWORD1);
			progKeywords.add("EDITOR-TAB", Token.KEYWORD1);
			progKeywords.add("ELSE", Token.KEYWORD1);
			progKeywords.add("EMPTY", Token.KEYWORD1);
			progKeywords.add("EMPTY-SELECTION", Token.KEYWORD1);
			progKeywords.add("EMPTY-TEMP-TABLE", Token.KEYWORD1);
			progKeywords.add("ENABLE", Token.KEYWORD1);
			progKeywords.add("ENABLE-CONNECTIONS", Token.KEYWORD1);
			progKeywords.add("ENABLED", Token.KEYWORD1);
			progKeywords.add("ENCODE", Token.KEYWORD1);
			progKeywords.add("ENCODING", Token.KEYWORD1);
			progKeywords.add("END", Token.KEYWORD1);
			progKeywords.add("END-BOX-SELECTION", Token.KEYWORD1);
			progKeywords.add("END-ERROR", Token.KEYWORD1);
			progKeywords.add("END-FILE-DROP", Token.KEYWORD1);
			progKeywords.add("END-KEY", Token.KEYWORD1);
			progKeywords.add("END-MOVE", Token.KEYWORD1);
			progKeywords.add("END-RESIZE", Token.KEYWORD1);
			progKeywords.add("END-ROW-RESIZE", Token.KEYWORD1);
			progKeywords.add("END-SEARCH", Token.KEYWORD1);
			progKeywords.add("END-USER-PROMPT", Token.KEYWORD1);
			progKeywords.add("ENDKEY", Token.KEYWORD1);
			progKeywords.add("ENTER-MENUBAR", Token.KEYWORD1);
			progKeywords.add("ENTERED", Token.KEYWORD1);
			progKeywords.add("ENTRY", Token.KEYWORD1);
			progKeywords.add("EQ", Token.KEYWORD1);
			progKeywords.add("ERROR", Token.KEYWORD1);
			progKeywords.add("ERROR-COLUMN", Token.KEYWORD1);
			progKeywords.add("ERROR-ROW", Token.KEYWORD1);
			progKeywords.add("ERROR-STATUS", Token.KEYWORD1);
			progKeywords.add("ESCAPE", Token.KEYWORD1);
			progKeywords.add("ETIME", Token.KEYWORD1);
			progKeywords.add("EVENT-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("EVENT-PROCEDURE-CONTEXT", Token.KEYWORD1);
			progKeywords.add("EVENT-TYPE", Token.KEYWORD1);
			progKeywords.add("EVENTS", Token.KEYWORD1);
			progKeywords.add("EXCEPT", Token.KEYWORD1);
			progKeywords.add("EXCLUSIVE", Token.KEYWORD1);
			progKeywords.add("EXCLUSIVE-ID", Token.KEYWORD1);
			progKeywords.add("EXCLUSIVE-LOCK", Token.KEYWORD1);
			progKeywords.add("EXCLUSIVE-WEB-USER", Token.KEYWORD1);
			progKeywords.add("EXECUTE", Token.KEYWORD1);
			progKeywords.add("EXECUTION-LOG", Token.KEYWORD1);
			progKeywords.add("EXISTS", Token.KEYWORD1);
			progKeywords.add("EXIT", Token.KEYWORD1);
			progKeywords.add("EXP", Token.KEYWORD1);
			progKeywords.add("EXPAND", Token.KEYWORD1);
			progKeywords.add("EXPANDABLE", Token.KEYWORD1);
			progKeywords.add("EXPLICIT", Token.KEYWORD1);
			progKeywords.add("EXPORT", Token.KEYWORD1);
			progKeywords.add("EXTENDED", Token.KEYWORD1);
			progKeywords.add("EXTENT", Token.KEYWORD1);
			progKeywords.add("EXTERNAL", Token.KEYWORD1);
			progKeywords.add("EXTRACT", Token.KEYWORD1);
			progKeywords.add("FALSE", Token.LITERAL2);
			progKeywords.add("FETCH", Token.KEYWORD1);
			progKeywords.add("FETCH-SELECTED-ROW", Token.KEYWORD1);
			progKeywords.add("FGCOLOR", Token.KEYWORD1);
			progKeywords.add("FIELDS", Token.KEYWORD1);
			progKeywords.add("FILE", Token.KEYWORD1);
			progKeywords.add("FILE-ACCESS-DATE", Token.KEYWORD1);
			progKeywords.add("FILE-ACCESS-TIME", Token.KEYWORD1);
			progKeywords.add("FILE-CREATE-DATE", Token.KEYWORD1);
			progKeywords.add("FILE-CREATE-TIME", Token.KEYWORD1);
			progKeywords.add("FILE-INFORMATION", Token.KEYWORD1);
			progKeywords.add("FILE-MOD-DATE", Token.KEYWORD1);
			progKeywords.add("FILE-MOD-TIME", Token.KEYWORD1);
			progKeywords.add("FILE-NAME", Token.KEYWORD1);
			progKeywords.add("FILE-OFFSET", Token.KEYWORD1);
			progKeywords.add("FILE-SIZE", Token.KEYWORD1);
			progKeywords.add("FILE-TYPE", Token.KEYWORD1);
			progKeywords.add("FILENAME", Token.KEYWORD1);
			progKeywords.add("FILL", Token.KEYWORD1);
			progKeywords.add("FILL-IN", Token.KEYWORD1);
			progKeywords.add("FILLED", Token.KEYWORD1);
			progKeywords.add("FILTERS", Token.KEYWORD1);
			progKeywords.add("FIND", Token.KEYWORD1);
			progKeywords.add("FIND-BY-ROWID", Token.KEYWORD1);
			progKeywords.add("FIND-CASE-SENSITIVE", Token.KEYWORD1);
			progKeywords.add("FIND-GLOBAL", Token.KEYWORD1);
			progKeywords.add("FIND-NEXT", Token.KEYWORD1);
			progKeywords.add("FIND-NEXT-OCCURRENCE", Token.KEYWORD1);
			progKeywords.add("FIND-PREV-OCCURRENCE", Token.KEYWORD1);
			progKeywords.add("FIND-PREVIOUS", Token.KEYWORD1);
			progKeywords.add("FIND-SELECT", Token.KEYWORD1);
			progKeywords.add("FIND-WRAP-AROUND", Token.KEYWORD1);
			progKeywords.add("FINDER", Token.KEYWORD1);
			progKeywords.add("FIRST", Token.KEYWORD1);
			progKeywords.add("FIRST-ASYNC-REQUEST", Token.KEYWORD1);
			progKeywords.add("FIRST-BUFFER", Token.KEYWORD1);
			progKeywords.add("FIRST-CHILD", Token.KEYWORD1);
			progKeywords.add("FIRST-COLUMN", Token.KEYWORD1);
			progKeywords.add("FIRST-OF", Token.KEYWORD1);
			progKeywords.add("FIRST-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("FIRST-SERVER", Token.KEYWORD1);
			progKeywords.add("FIRST-SERVER-SOCKET", Token.KEYWORD1);
			progKeywords.add("FIRST-SOCKET", Token.KEYWORD1);
			progKeywords.add("FIRST-TAB-ITEM", Token.KEYWORD1);
			progKeywords.add("FIXED-ONLY", Token.KEYWORD1);
			progKeywords.add("FLAT-BUTTON", Token.KEYWORD1);
			progKeywords.add("FLOAT", Token.KEYWORD1);
			progKeywords.add("FOCUS", Token.KEYWORD1);
			progKeywords.add("FOCUS-IN", Token.KEYWORD1);
			progKeywords.add("FOCUSED-ROW", Token.KEYWORD1);
			progKeywords.add("FOCUSED-ROW-SELECTED", Token.KEYWORD1);
			progKeywords.add("FONT", Token.KEYWORD1);
			progKeywords.add("FONT-TABLE", Token.KEYWORD1);
			progKeywords.add("FOR", Token.KEYWORD1);
			progKeywords.add("FORCE-FILE", Token.KEYWORD1);
			progKeywords.add("FOREGROUND", Token.KEYWORD1);
			progKeywords.add("FORMAT", Token.KEYWORD1);
			progKeywords.add("FORM-INPUT", Token.KEYWORD1);
			progKeywords.add("FORWARDS", Token.KEYWORD1);
			progKeywords.add("FRAME", Token.KEYWORD1);
			progKeywords.add("FRAME-COL", Token.KEYWORD1);
			progKeywords.add("FRAME-DB", Token.KEYWORD1);
			progKeywords.add("FRAME-DOWN", Token.KEYWORD1);
			progKeywords.add("FRAME-FIELD", Token.KEYWORD1);
			progKeywords.add("FRAME-FILE", Token.KEYWORD1);
			progKeywords.add("FRAME-INDEX", Token.KEYWORD1);
			progKeywords.add("FRAME-LINE", Token.KEYWORD1);
			progKeywords.add("FRAME-NAME", Token.KEYWORD1);
			progKeywords.add("FRAME-ROW", Token.KEYWORD1);
			progKeywords.add("FRAME-SPACING", Token.KEYWORD1);
			progKeywords.add("FRAME-VALUE", Token.KEYWORD1);
			progKeywords.add("FRAME-X", Token.KEYWORD1);
			progKeywords.add("FRAME-Y", Token.KEYWORD1);
			progKeywords.add("FREQUENCY", Token.KEYWORD1);
			progKeywords.add("FROM", Token.KEYWORD1);
			progKeywords.add("FROM-CHARS", Token.KEYWORD1);
			progKeywords.add("FROM-CURRENT", Token.KEYWORD1);
			progKeywords.add("FROM-PIXELS", Token.KEYWORD1);
			progKeywords.add("FROMNOREORDER", Token.KEYWORD1);
			progKeywords.add("FULL-HEIGHT", Token.KEYWORD1);
			progKeywords.add("FULL-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("FULL-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("FULL-PATHNAME", Token.KEYWORD1);
			progKeywords.add("FULL-WIDTH-CHARS", Token.KEYWORD1);
			progKeywords.add("FULL-WIDTH-PIXELS", Token.KEYWORD1);
			progKeywords.add("FUNCTION", Token.KEYWORD1);
			progKeywords.add("GATEWAYS", Token.KEYWORD1);
			progKeywords.add("GE", Token.KEYWORD1);
			progKeywords.add("GENERATE-MD5", Token.KEYWORD1);
			progKeywords.add("GET", Token.KEYWORD2);
			progKeywords.add("GET-ATTRIBUTE", Token.KEYWORD2);
			progKeywords.add("GET-ATTRIBUTE-NODE", Token.KEYWORD2);
			progKeywords.add("GET-BITS", Token.KEYWORD2);
			progKeywords.add("GET-BLUE-VALUE", Token.KEYWORD2);
			progKeywords.add("GET-BROWSE-COLUMN", Token.KEYWORD2);
			progKeywords.add("GET-BUFFER-HANDLE", Token.KEYWORD2);
			progKeywords.add("GET-BYTE", Token.KEYWORD2);
			progKeywords.add("GET-BYTE-ORDER", Token.KEYWORD2);
			progKeywords.add("GET-BYTES", Token.KEYWORD2);
			progKeywords.add("GET-BYTES-AVAILABLE", Token.KEYWORD2);
			progKeywords.add("GET-CGI-LIST", Token.KEYWORD2);
			progKeywords.add("GET-CGI-VALUE", Token.KEYWORD2);
			progKeywords.add("GET-CHILD", Token.KEYWORD2);
			progKeywords.add("GET-CODEPAGES", Token.KEYWORD2);
			progKeywords.add("GET-COLLATIONS", Token.KEYWORD2);
			progKeywords.add("GET-CONFIG-VALUE", Token.KEYWORD2);
			progKeywords.add("GET-CURRENT", Token.KEYWORD2);
			progKeywords.add("GET-DOCUMENT-ELEMENT", Token.KEYWORD2);
			progKeywords.add("GET-DOUBLE", Token.KEYWORD2);
			progKeywords.add("GET-DROPPED-FILE", Token.KEYWORD2);
			progKeywords.add("GET-DYNAMIC", Token.KEYWORD2);
			progKeywords.add("GET-FILE", Token.KEYWORD2);
			progKeywords.add("GET-FIRST", Token.KEYWORD2);
			progKeywords.add("GET-FLOAT", Token.KEYWORD2);
			progKeywords.add("GET-GREEN-VALUE", Token.KEYWORD2);
			progKeywords.add("GET-ITERATION", Token.KEYWORD2);
			progKeywords.add("GET-KEY-VALUE", Token.KEYWORD2);
			progKeywords.add("GET-LAST", Token.KEYWORD2);
			progKeywords.add("GET-LONG", Token.KEYWORD2);
			progKeywords.add("GET-MESSAGE", Token.KEYWORD2);
			progKeywords.add("GET-NEXT", Token.KEYWORD2);
			progKeywords.add("GET-NUMBER", Token.KEYWORD2);
			progKeywords.add("GET-PARENT", Token.KEYWORD2);
			progKeywords.add("GET-POINTER-VALUE", Token.KEYWORD2);
			progKeywords.add("GET-PREV", Token.KEYWORD2);
			progKeywords.add("GET-PRINTERS", Token.KEYWORD2);
			progKeywords.add("GET-RED-VALUE", Token.KEYWORD2);
			progKeywords.add("GET-REPOSITIONED-ROW", Token.KEYWORD2);
			progKeywords.add("GET-RGB-VALUE", Token.KEYWORD2);
			progKeywords.add("GET-SELECTED-WIDGET", Token.KEYWORD2);
			progKeywords.add("GET-SHORT", Token.KEYWORD2);
			progKeywords.add("GET-SIGNATURE", Token.KEYWORD2);
			progKeywords.add("GET-SIZE", Token.KEYWORD2);
			progKeywords.add("GET-SOCKET-OPTION", Token.KEYWORD2);
			progKeywords.add("GET-STRING", Token.KEYWORD2);
			progKeywords.add("GET-TAB-ITEM", Token.KEYWORD2);
			progKeywords.add("GET-TEXT-HEIGHT", Token.KEYWORD2);
			progKeywords.add("GET-TEXT-HEIGHT-CHARS", Token.KEYWORD2);
			progKeywords.add("GET-TEXT-HEIGHT-PIXELS", Token.KEYWORD2);
			progKeywords.add("GET-TEXT-WIDTH", Token.KEYWORD2);
			progKeywords.add("GET-TEXT-WIDTH-CHARS", Token.KEYWORD2);
			progKeywords.add("GET-TEXT-WIDTH-PIXELS", Token.KEYWORD2);
			progKeywords.add("GET-UNSIGNED-SHORT", Token.KEYWORD2);
			progKeywords.add("GET-WAIT-STATE", Token.KEYWORD2);
			progKeywords.add("GETBYTE", Token.KEYWORD2);
			progKeywords.add("GLOBAL", Token.KEYWORD1);
			progKeywords.add("GO", Token.KEYWORD1);
			progKeywords.add("GO-ON", Token.KEYWORD1);
			progKeywords.add("GO-PENDING", Token.KEYWORD1);
			progKeywords.add("GOTO", Token.KEYWORD1);
			progKeywords.add("GRANT", Token.KEYWORD1);
			progKeywords.add("GRAPHIC-EDGE", Token.KEYWORD1);
			progKeywords.add("GRAYED", Token.KEYWORD1);
			progKeywords.add("GRID-FACTOR-HORIZONTAL", Token.KEYWORD1);
			progKeywords.add("GRID-FACTOR-VERTICAL", Token.KEYWORD1);
			progKeywords.add("GRID-SET", Token.KEYWORD1);
			progKeywords.add("GRID-SNAP", Token.KEYWORD1);
			progKeywords.add("GRID-UNIT-HEIGHT", Token.KEYWORD1);
			progKeywords.add("GRID-UNIT-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("GRID-UNIT-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("GRID-UNIT-WIDTH", Token.KEYWORD1);
			progKeywords.add("GRID-UNIT-WIDTH-CHARS", Token.KEYWORD1);
			progKeywords.add("GRID-UNIT-WIDTH-PIXELS", Token.KEYWORD1);
			progKeywords.add("GRID-VISIBLE", Token.KEYWORD1);
			progKeywords.add("GROUP", Token.KEYWORD1);
			progKeywords.add("GT", Token.KEYWORD1);
			progKeywords.add("HANDLE", Token.KEYWORD1);
			progKeywords.add("HAS-RECORDS", Token.KEYWORD1);
			progKeywords.add("HAVING", Token.KEYWORD1);
			progKeywords.add("HEADER", Token.KEYWORD1);
			progKeywords.add("HEIGHT", Token.KEYWORD1);
			progKeywords.add("HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("HELP", Token.KEYWORD1);
			progKeywords.add("HELP-CONTEXT", Token.KEYWORD1);
			progKeywords.add("HELP-TOPIC", Token.KEYWORD1);
			progKeywords.add("HELPFILE-NAME", Token.KEYWORD1);
			progKeywords.add("HIDDEN", Token.KEYWORD1);
			progKeywords.add("HIDE", Token.KEYWORD1);
			progKeywords.add("HINT", Token.KEYWORD1);
			progKeywords.add("HOME", Token.KEYWORD1);
			progKeywords.add("HORIZONTAL", Token.KEYWORD1);
			progKeywords.add("HORIZ-END", Token.KEYWORD1);
			progKeywords.add("HORIZ-HOME", Token.KEYWORD1);
			progKeywords.add("HORIZ-SCROLL-DRAG", Token.KEYWORD1);
			progKeywords.add("HOST-BYTE-ORDER", Token.KEYWORD1);
			progKeywords.add("HTML-END-OF-LINE", Token.KEYWORD1);
			progKeywords.add("HTML-END-OF-PAGE", Token.KEYWORD1);
			progKeywords.add("HTML-FRAME-BEGIN", Token.KEYWORD1);
			progKeywords.add("HTML-FRAME-END", Token.KEYWORD1);
			progKeywords.add("HTML-HEADER-BEGIN", Token.KEYWORD1);
			progKeywords.add("HTML-HEADER-END", Token.KEYWORD1);
			progKeywords.add("HTML-TITLE-BEGIN", Token.KEYWORD1);
			progKeywords.add("HTML-TITLE-END", Token.KEYWORD1);
			progKeywords.add("HWND", Token.KEYWORD1);
			progKeywords.add("ICFPARAMETER", Token.KEYWORD1);
			progKeywords.add("ICON", Token.KEYWORD1);
			progKeywords.add("IF", Token.KEYWORD1);
			progKeywords.add("IMAGE", Token.KEYWORD1);
			progKeywords.add("IMAGE-DOWN", Token.KEYWORD1);
			progKeywords.add("IMAGE-INSENSITIVE", Token.KEYWORD1);
			progKeywords.add("IMAGE-SIZE", Token.KEYWORD1);
			progKeywords.add("IMAGE-SIZE-CHARS", Token.KEYWORD1);
			progKeywords.add("IMAGE-SIZE-PIXELS", Token.KEYWORD1);
			progKeywords.add("IMAGE-UP", Token.KEYWORD1);
			progKeywords.add("IMMEDIATE-DISPLAY", Token.KEYWORD1);
			progKeywords.add("IMPORT", Token.KEYWORD1);
			progKeywords.add("IMPORT-NODE", Token.KEYWORD1);
			progKeywords.add("IN", Token.KEYWORD1);
			progKeywords.add("INCREMENT-EXCLUSIVE-ID", Token.KEYWORD1);
			progKeywords.add("INDEX", Token.KEYWORD1);
			progKeywords.add("INDEX-HINT", Token.KEYWORD1);
			progKeywords.add("INDEX-INFORMATION", Token.KEYWORD1);
			progKeywords.add("INDEXED-REPOSITION", Token.KEYWORD1);
			progKeywords.add("INDICATOR", Token.KEYWORD1);
			progKeywords.add("INFORMATION", Token.KEYWORD1);
			progKeywords.add("INIT", Token.KEYWORD1);
			progKeywords.add("INITIAL", Token.KEYWORD1);
			progKeywords.add("INITIAL-DIR", Token.KEYWORD1);
			progKeywords.add("INITIAL-FILTER", Token.KEYWORD1);
			progKeywords.add("INITIALIZE-DOCUMENT-TYPE", Token.KEYWORD1);
			progKeywords.add("INITIATE", Token.KEYWORD1);
			progKeywords.add("INNER", Token.KEYWORD1);
			progKeywords.add("INNER-CHARS", Token.KEYWORD1);
			progKeywords.add("INNER-LINES", Token.KEYWORD1);
			progKeywords.add("INPUT", Token.KEYWORD1);
			progKeywords.add("INPUT-OUTPUT", Token.KEYWORD1);
			progKeywords.add("INPUT-VALUE", Token.KEYWORD1);
			progKeywords.add("INSERT", Token.KEYWORD1);
			progKeywords.add("INSERT-BACKTAB", Token.KEYWORD1);
			progKeywords.add("INSERT-BEFORE", Token.KEYWORD1);
			progKeywords.add("INSERT-COLUMN", Token.KEYWORD1);
			progKeywords.add("INSERT-FIELD", Token.KEYWORD1);
			progKeywords.add("INSERT-FIELD-DATA", Token.KEYWORD1);
			progKeywords.add("INSERT-FIELD-LABEL", Token.KEYWORD1);
			progKeywords.add("INSERT-FILE", Token.KEYWORD1);
			progKeywords.add("INSERT-MODE", Token.KEYWORD1);
			progKeywords.add("INSERT-ROW", Token.KEYWORD1);
			progKeywords.add("INSERT-STRING", Token.KEYWORD1);
			progKeywords.add("INSERT-TAB", Token.KEYWORD1);
			progKeywords.add("INTEGER", Token.KEYWORD1);
			progKeywords.add("INTERNAL-ENTRIES", Token.KEYWORD1);
			progKeywords.add("INTO", Token.KEYWORD1);
			progKeywords.add("IS", Token.KEYWORD1);
			progKeywords.add("IS-ATTR-SPACE", Token.KEYWORD1);
			progKeywords.add("IS-LEAD-BYTE", Token.KEYWORD1);
			progKeywords.add("IS-OPEN", Token.KEYWORD1);
			progKeywords.add("IS-ROW-SELECTED", Token.KEYWORD1);
			progKeywords.add("IS-SELECTED", Token.KEYWORD1);
			progKeywords.add("IS-XML", Token.KEYWORD1);
			progKeywords.add("ITEM", Token.KEYWORD1);
			progKeywords.add("ITEMS-PER-ROW", Token.KEYWORD1);
			progKeywords.add("ITERATION-CHANGED", Token.KEYWORD1);
			progKeywords.add("JOIN", Token.KEYWORD1);
			progKeywords.add("JOIN-BY-SQLDB", Token.KEYWORD1);
			progKeywords.add("KBLABEL", Token.KEYWORD1);
			progKeywords.add("KEEP-CONNECTION-OPEN", Token.KEYWORD1);
			progKeywords.add("KEEP-FRAME-Z-ORDER", Token.KEYWORD1);
			progKeywords.add("KEEP-MESSAGES", Token.KEYWORD1);
			progKeywords.add("KEEP-SECURITY-CACHE", Token.KEYWORD1);
			progKeywords.add("KEEP-TAB-ORDER", Token.KEYWORD1);
			progKeywords.add("KEY", Token.KEYWORD1);
			progKeywords.add("KEY-CODE", Token.KEYWORD1);
			progKeywords.add("KEY-FUNCTION", Token.KEYWORD1);
			progKeywords.add("KEY-LABEL", Token.KEYWORD1);
			progKeywords.add("KEYCODE", Token.KEYWORD1);
			progKeywords.add("KEYFUNCTION", Token.KEYWORD1);
			progKeywords.add("KEYLABEL", Token.KEYWORD1);
			progKeywords.add("KEYS", Token.KEYWORD1);
			progKeywords.add("KEYWORD", Token.KEYWORD1);
			progKeywords.add("KEYWORD-ALL", Token.KEYWORD1);
			progKeywords.add("LABEL", Token.KEYWORD1);
			progKeywords.add("LABEL-BGCOLOR", Token.KEYWORD1);
			progKeywords.add("LABEL-DCOLOR", Token.KEYWORD1);
			progKeywords.add("LABEL-FGCOLOR", Token.KEYWORD1);
			progKeywords.add("LABEL-FONT", Token.KEYWORD1);
			progKeywords.add("LABEL-PFCOLOR", Token.KEYWORD1);
			progKeywords.add("LABELS", Token.KEYWORD1);
			progKeywords.add("LANDSCAPE", Token.KEYWORD1);
			progKeywords.add("LANGUAGES", Token.KEYWORD1);
			progKeywords.add("LARGE", Token.KEYWORD1);
			progKeywords.add("LARGE-TO-SMALL", Token.KEYWORD1);
			progKeywords.add("LAST", Token.KEYWORD1);
			progKeywords.add("LAST-ASYNC-REQUEST", Token.KEYWORD1);
			progKeywords.add("LAST-CHILD", Token.KEYWORD1);
			progKeywords.add("LAST-EVENT", Token.KEYWORD1);
			progKeywords.add("LAST-KEY", Token.KEYWORD1);
			progKeywords.add("LAST-OF", Token.KEYWORD1);
			progKeywords.add("LAST-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("LAST-SERVER", Token.KEYWORD1);
			progKeywords.add("LAST-SERVER-SOCKET", Token.KEYWORD1);
			progKeywords.add("LAST-SOCKET", Token.KEYWORD1);
			progKeywords.add("LAST-TAB-ITEM", Token.KEYWORD1);
			progKeywords.add("LASTKEY", Token.KEYWORD1);
			progKeywords.add("LC", Token.KEYWORD1);
			progKeywords.add("LDBNAME", Token.KEYWORD1);
			progKeywords.add("LE", Token.KEYWORD1);
			progKeywords.add("LEADING", Token.KEYWORD1);
			progKeywords.add("LEAVE", Token.KEYWORD1);
			progKeywords.add("LEFT", Token.KEYWORD1);
			progKeywords.add("LEFT-ALIGNED", Token.KEYWORD1);
			progKeywords.add("LEFT-END", Token.KEYWORD1);
			progKeywords.add("LEFT-TRIM", Token.KEYWORD1);
			progKeywords.add("LENGTH", Token.KEYWORD1);
			progKeywords.add("LIBRARY", Token.KEYWORD1);
			progKeywords.add("LIKE", Token.KEYWORD1);
			progKeywords.add("LINE", Token.KEYWORD1);
			progKeywords.add("LINE-COUNTER", Token.KEYWORD1);
			progKeywords.add("LINE-DOWN", Token.KEYWORD1);
			progKeywords.add("LINE-LEFT", Token.KEYWORD1);
			progKeywords.add("LINE-RIGHT", Token.KEYWORD1);
			progKeywords.add("LINE-UP", Token.KEYWORD1);
			progKeywords.add("LIST-EVENTS", Token.KEYWORD1);
			progKeywords.add("LIST-ITEM-PAIRS", Token.KEYWORD1);
			progKeywords.add("LIST-ITEMS", Token.KEYWORD1);
			progKeywords.add("LIST-QUERY-ATTRS", Token.KEYWORD1);
			progKeywords.add("LIST-SET-ATTRS", Token.KEYWORD1);
			progKeywords.add("LIST-WIDGETS", Token.KEYWORD1);
			progKeywords.add("LISTING", Token.KEYWORD1);
			progKeywords.add("LISTINGS", Token.KEYWORD1);
			progKeywords.add("LITTLE-ENDIAN", Token.KEYWORD1);
			progKeywords.add("LOAD", Token.KEYWORD1);
			progKeywords.add("LOAD-FROM", Token.KEYWORD1);
			progKeywords.add("LOAD-ICON", Token.KEYWORD1);
			progKeywords.add("LOAD-IMAGE", Token.KEYWORD1);
			progKeywords.add("LOAD-IMAGE-DOWN", Token.KEYWORD1);
			progKeywords.add("LOAD-IMAGE-INSENSITIVE", Token.KEYWORD1);
			progKeywords.add("LOAD-IMAGE-UP", Token.KEYWORD1);
			progKeywords.add("LOAD-MOUSE-POINTER", Token.KEYWORD1);
			progKeywords.add("LOAD-PICTURE", Token.KEYWORD1);
			progKeywords.add("LOAD-SMALL-ICON", Token.KEYWORD1);
			progKeywords.add("LOCAL-HOST", Token.KEYWORD1);
			progKeywords.add("LOCAL-NAME", Token.KEYWORD1);
			progKeywords.add("LOCAL-PORT", Token.KEYWORD1);
			progKeywords.add("LOCATOR-TYPE", Token.KEYWORD1);
			progKeywords.add("LOCKED", Token.KEYWORD1);
			progKeywords.add("LOG", Token.KEYWORD1);
			progKeywords.add("LOG-ID", Token.KEYWORD1);
			progKeywords.add("LOGICAL", Token.KEYWORD1);
			progKeywords.add("LONG", Token.KEYWORD1);
			progKeywords.add("LOOKAHEAD", Token.KEYWORD1);
			progKeywords.add("LOOKUP", Token.KEYWORD1);
			progKeywords.add("LOWER", Token.KEYWORD1);
			progKeywords.add("LT", Token.KEYWORD1);
			progKeywords.add("MACHINE-CLASS", Token.KEYWORD1);
			progKeywords.add("MAIN-MENU", Token.KEYWORD1);
			progKeywords.add("MANDATORY", Token.KEYWORD1);
			progKeywords.add("MANUAL-HIGHLIGHT", Token.KEYWORD1);
			progKeywords.add("MAP", Token.KEYWORD1);
			progKeywords.add("MARGIN-EXTRA", Token.KEYWORD1);
			progKeywords.add("MARGIN-HEIGHT", Token.KEYWORD1);
			progKeywords.add("MARGIN-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("MARGIN-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("MARGIN-WIDTH", Token.KEYWORD1);
			progKeywords.add("MARGIN-WIDTH-CHARS", Token.KEYWORD1);
			progKeywords.add("MARGIN-WIDTH-PIXELS", Token.KEYWORD1);
			progKeywords.add("MATCHES", Token.KEYWORD1);
			progKeywords.add("MAX", Token.KEYWORD1);
			progKeywords.add("MAX-BUTTON", Token.KEYWORD1);
			progKeywords.add("MAX-CHARS", Token.KEYWORD1);
			progKeywords.add("MAX-DATA-GUESS", Token.KEYWORD1);
			progKeywords.add("MAX-HEIGHT", Token.KEYWORD1);
			progKeywords.add("MAX-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("MAX-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("MAX-ROWS", Token.KEYWORD1);
			progKeywords.add("MAX-SIZE", Token.KEYWORD1);
			progKeywords.add("MAX-VALUE", Token.KEYWORD1);
			progKeywords.add("MAX-WIDTH", Token.KEYWORD1);
			progKeywords.add("MAX-WIDTH-CHARS", Token.KEYWORD1);
			progKeywords.add("MAX-WIDTH-PIXELS", Token.KEYWORD1);
			progKeywords.add("MAXIMIZE", Token.KEYWORD1);
			progKeywords.add("MAXIMUM", Token.KEYWORD1);
			progKeywords.add("MEMBER", Token.KEYWORD1);
			progKeywords.add("MEMPTR", Token.KEYWORD1);
			progKeywords.add("MENU", Token.KEYWORD1);
			progKeywords.add("MENU-BAR", Token.KEYWORD1);
			progKeywords.add("MENU-DROP", Token.KEYWORD1);
			progKeywords.add("MENU-ITEM", Token.KEYWORD1);
			progKeywords.add("MENU-KEY", Token.KEYWORD1);
			progKeywords.add("MENU-MOUSE", Token.KEYWORD1);
			progKeywords.add("MENUBAR", Token.KEYWORD1);
			progKeywords.add("MESSAGE", Token.KEYWORD1);
			progKeywords.add("MESSAGE-AREA", Token.KEYWORD1);
			progKeywords.add("MESSAGE-AREA-FONT", Token.KEYWORD1);
			progKeywords.add("MESSAGE-LINE", Token.KEYWORD1);
			progKeywords.add("MESSAGE-LINES", Token.KEYWORD1);
			progKeywords.add("MINIMUM", Token.KEYWORD1);
			progKeywords.add("MIN-BUTTON", Token.KEYWORD1);
			progKeywords.add("MIN-HEIGHT", Token.KEYWORD1);
			progKeywords.add("MIN-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("MIN-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("MIN-ROW-HEIGHT", Token.KEYWORD1);
			progKeywords.add("MIN-ROW-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("MIN-ROW-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("MIN-SIZE", Token.KEYWORD1);
			progKeywords.add("MIN-VALUE", Token.KEYWORD1);
			progKeywords.add("MIN-WIDTH", Token.KEYWORD1);
			progKeywords.add("MIN-WIDTH-CHARS", Token.KEYWORD1);
			progKeywords.add("MIN-WIDTH-PIXELS", Token.KEYWORD1);
			progKeywords.add("MOD", Token.KEYWORD1);
			progKeywords.add("MODIFIED", Token.KEYWORD1);
			progKeywords.add("MODULO", Token.KEYWORD1);
			progKeywords.add("MONTH", Token.KEYWORD1);
			progKeywords.add("MOUSE", Token.KEYWORD1);
			progKeywords.add("MOUSE-POINTER", Token.KEYWORD1);
			progKeywords.add("MOVABLE", Token.KEYWORD1);
			progKeywords.add("MOVE", Token.KEYWORD1);
			progKeywords.add("MOVE-AFTER-TAB-ITEM", Token.KEYWORD1);
			progKeywords.add("MOVE-BEFORE-TAB-ITEM", Token.KEYWORD1);
			progKeywords.add("MOVE-COLUMN", Token.KEYWORD1);
			progKeywords.add("MOVE-TO-BOTTOM", Token.KEYWORD1);
			progKeywords.add("MOVE-TO-EOF", Token.KEYWORD1);
			progKeywords.add("MOVE-TO-TOP", Token.KEYWORD1);
			progKeywords.add("MPE", Token.KEYWORD1);
			progKeywords.add("MULTIPLE", Token.KEYWORD1);
			progKeywords.add("MULTIPLE-KEY", Token.KEYWORD1);
			progKeywords.add("MULTITASKING-INTERVAL", Token.KEYWORD1);
			progKeywords.add("MUST-EXIST", Token.KEYWORD1);
			progKeywords.add("mysearchablewidget", Token.KEYWORD1);
			progKeywords.add("NAME", Token.KEYWORD1);
			progKeywords.add("NAMESPACE-PREFIX", Token.KEYWORD1);
			progKeywords.add("NAMESPACE-URI", Token.KEYWORD1);
			progKeywords.add("NATIVE", Token.KEYWORD1);
			progKeywords.add("NE", Token.KEYWORD1);
			progKeywords.add("NEEDS-APPSERVER-PROMPT", Token.KEYWORD1);
			progKeywords.add("NEEDS-PROMPT", Token.KEYWORD1);
			progKeywords.add("NEW", Token.KEYWORD1);
			progKeywords.add("NEW-LINE", Token.KEYWORD1);
			progKeywords.add("NEW-ROW", Token.KEYWORD1);
			progKeywords.add("NEXT", Token.KEYWORD1);
			progKeywords.add("NEXT-COLUMN", Token.KEYWORD1);
			progKeywords.add("NEXT-ERROR", Token.KEYWORD1);
			progKeywords.add("NEXT-FRAME", Token.KEYWORD1);
			progKeywords.add("NEXT-PROMPT", Token.KEYWORD1);
			progKeywords.add("NEXT-SIBLING", Token.KEYWORD1);
			progKeywords.add("NEXT-TAB-ITEM", Token.KEYWORD1);
			progKeywords.add("NEXT-VALUE", Token.KEYWORD1);
			progKeywords.add("NEXT-WORD", Token.KEYWORD1);
			progKeywords.add("NO", Token.KEYWORD1);
			progKeywords.add("NO-APPLY", Token.KEYWORD1);
			progKeywords.add("NO-ARRAY-MESSAGE", Token.KEYWORD1);
			progKeywords.add("NO-ASSIGN", Token.KEYWORD1);
			progKeywords.add("NO-ATTR", Token.KEYWORD1);
			progKeywords.add("NO-ATTR-LIST", Token.KEYWORD1);
			progKeywords.add("NO-ATTR-SPACE", Token.KEYWORD1);
			progKeywords.add("NO-AUTO-VALIDATE", Token.KEYWORD1);
			progKeywords.add("NO-BIND-WHERE", Token.KEYWORD1);
			progKeywords.add("NO-BOX", Token.KEYWORD1);
			progKeywords.add("NO-COLUMN-SCROLLING", Token.KEYWORD1);
			progKeywords.add("NO-CONSOLE", Token.KEYWORD1);
			progKeywords.add("NO-CONVERT", Token.KEYWORD1);
			progKeywords.add("NO-CONVERT-3D-COLORS", Token.KEYWORD1);
			progKeywords.add("NO-CURRENT-VALUE", Token.KEYWORD1);
			progKeywords.add("NO-DEBUG", Token.KEYWORD1);
			progKeywords.add("NO-DRAG", Token.KEYWORD1);
			progKeywords.add("NO-ECHO", Token.KEYWORD1);
			progKeywords.add("NO-ERROR", Token.KEYWORD1);
			progKeywords.add("NO-FILL", Token.KEYWORD1);
			progKeywords.add("NO-FOCUS", Token.KEYWORD1);
			progKeywords.add("NO-HELP", Token.KEYWORD1);
			progKeywords.add("NO-HIDE", Token.KEYWORD1);
			progKeywords.add("NO-INDEX-HINT", Token.KEYWORD1);
			progKeywords.add("NO-JOIN-BY-SQLDB", Token.KEYWORD1);
			progKeywords.add("NO-LABELS", Token.KEYWORD1);
			progKeywords.add("NO-LOCK", Token.KEYWORD1);
			progKeywords.add("NO-LOOKAHEAD", Token.KEYWORD1);
			progKeywords.add("NO-MAP", Token.KEYWORD1);
			progKeywords.add("NO-MESSAGE", Token.KEYWORD1);
			progKeywords.add("NO-PAUSE", Token.KEYWORD1);
			progKeywords.add("NO-PREFETCH", Token.KEYWORD1);
			progKeywords.add("NO-RETURN-VALUE", Token.KEYWORD1);
			progKeywords.add("NO-ROW-MARKERS", Token.KEYWORD1);
			progKeywords.add("NO-SCROLLBAR-VERTICAL", Token.KEYWORD1);
			progKeywords.add("NO-SCROLLING", Token.KEYWORD1);
			progKeywords.add("NO-SEPARATE-CONNECTION", Token.KEYWORD1);
			progKeywords.add("NO-SEPARATORS", Token.KEYWORD1);
			progKeywords.add("NO-TAB-STOP", Token.KEYWORD1);
			progKeywords.add("NO-UNDERLINE", Token.KEYWORD1);
			progKeywords.add("NO-UNDO", Token.KEYWORD1);
			progKeywords.add("NO-VALIDATE", Token.KEYWORD1);
			progKeywords.add("NO-WAIT", Token.KEYWORD1);
			progKeywords.add("NO-WORD-WRAP", Token.KEYWORD1);
			progKeywords.add("NODE-TYPE", Token.KEYWORD1);
			progKeywords.add("NODE-VALUE", Token.KEYWORD1);
			progKeywords.add("NONE", Token.KEYWORD1);
			progKeywords.add("NORMALIZE", Token.KEYWORD1);
			progKeywords.add("NOT", Token.KEYWORD1);
			progKeywords.add("NULL", Token.KEYWORD1);
			progKeywords.add("NUM-ALIASES", Token.KEYWORD1);
			progKeywords.add("NUM-BUFFERS", Token.KEYWORD1);
			progKeywords.add("NUM-BUTTONS", Token.KEYWORD1);
			progKeywords.add("NUM-CHILDREN", Token.KEYWORD1);
			progKeywords.add("NUM-COLUMNS", Token.KEYWORD1);
			progKeywords.add("NUM-COPIES", Token.KEYWORD1);
			progKeywords.add("NUM-DBS", Token.KEYWORD1);
			progKeywords.add("NUM-DROPPED-FILES", Token.KEYWORD1);
			progKeywords.add("NUM-ENTRIES", Token.KEYWORD1);
			progKeywords.add("NUM-FIELDS", Token.KEYWORD1);
			progKeywords.add("NUM-FORMATS", Token.KEYWORD1);
			progKeywords.add("NUM-ITEMS", Token.KEYWORD1);
			progKeywords.add("NUM-ITERATIONS", Token.KEYWORD1);
			progKeywords.add("NUM-LINES", Token.KEYWORD1);
			progKeywords.add("NUM-LOCKED-COLUMNS", Token.KEYWORD1);
			progKeywords.add("NUM-MESSAGES", Token.KEYWORD1);
			progKeywords.add("NUM-REPLACED", Token.KEYWORD1);
			progKeywords.add("NUM-RESULTS", Token.KEYWORD1);
			progKeywords.add("NUM-SELECTED", Token.KEYWORD1);
			progKeywords.add("NUM-SELECTED-ROWS", Token.KEYWORD1);
			progKeywords.add("NUM-SELECTED-WIDGETS", Token.KEYWORD1);
			progKeywords.add("NUM-TABS", Token.KEYWORD1);
			progKeywords.add("NUM-TO-RETAIN", Token.KEYWORD1);
			progKeywords.add("NUM-VISIBLE-COLUMNS", Token.KEYWORD1);
			progKeywords.add("NUMERIC", Token.KEYWORD1);
			progKeywords.add("NUMERIC-DECIMAL-POINT", Token.KEYWORD1);
			progKeywords.add("NUMERIC-FORMAT", Token.KEYWORD1);
			progKeywords.add("NUMERIC-SEPARATOR", Token.KEYWORD1);
			progKeywords.add("OBJECT", Token.KEYWORD1);
			progKeywords.add("OCTET_LENGTH", Token.KEYWORD1);
			progKeywords.add("OF", Token.KEYWORD1);
			progKeywords.add("OFF", Token.KEYWORD1);
			progKeywords.add("OFF-END", Token.KEYWORD1);
			progKeywords.add("OFF-HOME", Token.KEYWORD1);
			progKeywords.add("OK", Token.KEYWORD1);
			progKeywords.add("OK-CANCEL", Token.KEYWORD1);
			progKeywords.add("OLD", Token.KEYWORD1);
			progKeywords.add("OLE-INVOKE-LOCALE", Token.KEYWORD1);
			progKeywords.add("OLE-NAMES-LOCALE", Token.KEYWORD1);
			progKeywords.add("ON", Token.KEYWORD1);
			progKeywords.add("ON-FRAME-BORDER", Token.KEYWORD1);
			progKeywords.add("OPEN", Token.KEYWORD1);
			progKeywords.add("OPEN-LINE-ABOVE", Token.KEYWORD1);
			progKeywords.add("OPSYS", Token.KEYWORD1);
			progKeywords.add("OPTION", Token.KEYWORD1);
			progKeywords.add("OPTIONS", Token.KEYWORD1);
			progKeywords.add("OR", Token.KEYWORD1);
			progKeywords.add("ORDERED-JOIN", Token.KEYWORD1);
			progKeywords.add("ORDINAL", Token.KEYWORD1);
			progKeywords.add("ORIENTATION", Token.KEYWORD1);
			progKeywords.add("OS-APPEND", Token.KEYWORD1);
			progKeywords.add("OS-COMMAND", Token.KEYWORD1);
			progKeywords.add("OS-COPY", Token.KEYWORD1);
			progKeywords.add("OS-CREATE-DIR", Token.KEYWORD1);
			progKeywords.add("OS-DELETE", Token.KEYWORD1);
			progKeywords.add("OS-DIR", Token.KEYWORD1);
			progKeywords.add("OS-DRIVES", Token.KEYWORD1);
			progKeywords.add("OS-ERROR", Token.KEYWORD1);
			progKeywords.add("OS-GETENV", Token.KEYWORD1);
			progKeywords.add("OS-RENAME", Token.KEYWORD1);
			progKeywords.add("OS2", Token.KEYWORD1);
			progKeywords.add("OS400", Token.KEYWORD1);
			progKeywords.add("OTHERWISE", Token.KEYWORD1);
			progKeywords.add("OUT-OF-DATA", Token.KEYWORD1);
			progKeywords.add("OUTER", Token.KEYWORD1);
			progKeywords.add("OUTER-JOIN", Token.KEYWORD1);
			progKeywords.add("OUTPUT", Token.KEYWORD1);
			progKeywords.add("OVERLAY", Token.KEYWORD1);
			progKeywords.add("OVERRIDE", Token.KEYWORD1);
			progKeywords.add("OWNER", Token.KEYWORD1);
			progKeywords.add("OWNER-DOCUMENT", Token.KEYWORD1);
			progKeywords.add("PAGE", Token.KEYWORD1);
			progKeywords.add("PAGE-BOTTOM", Token.KEYWORD1);
			progKeywords.add("PAGE-DOWN", Token.KEYWORD1);
			progKeywords.add("PAGE-LEFT", Token.KEYWORD1);
			progKeywords.add("PAGE-NUMBER", Token.KEYWORD1);
			progKeywords.add("PAGE-RIGHT", Token.KEYWORD1);
			progKeywords.add("PAGE-RIGHT-TEXT", Token.KEYWORD1);
			progKeywords.add("PAGE-SIZE", Token.KEYWORD1);
			progKeywords.add("PAGE-TOP", Token.KEYWORD1);
			progKeywords.add("PAGE-UP", Token.KEYWORD1);
			progKeywords.add("PAGE-WIDTH", Token.KEYWORD1);
			progKeywords.add("PAGED", Token.KEYWORD1);
			progKeywords.add("PARAMETER", Token.KEYWORD1);
			progKeywords.add("PARENT", Token.KEYWORD1);
			progKeywords.add("PARENT-WINDOW-CLOSE", Token.KEYWORD1);
			progKeywords.add("PARTIAL-KEY", Token.KEYWORD1);
			progKeywords.add("PASCAL", Token.KEYWORD1);
			progKeywords.add("PASTE", Token.KEYWORD1);
			progKeywords.add("PATHNAME", Token.KEYWORD1);
			progKeywords.add("PAUSE", Token.KEYWORD1);
			progKeywords.add("PDBNAME", Token.KEYWORD1);
			progKeywords.add("PERFORMANCE", Token.KEYWORD1);
			progKeywords.add("PERSISTENT", Token.KEYWORD1);
			progKeywords.add("PERSISTENT-CACHE-DISABLED", Token.KEYWORD1);
			progKeywords.add("PERSISTENT-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("PFCOLOR", Token.KEYWORD1);
			progKeywords.add("PICK", Token.KEYWORD1);
			progKeywords.add("PICK-AREA", Token.KEYWORD1);
			progKeywords.add("PICK-BOTH", Token.KEYWORD1);
			progKeywords.add("PIXELS", Token.KEYWORD1);
			progKeywords.add("PIXELS-PER-COLUMN", Token.KEYWORD1);
			progKeywords.add("PIXELS-PER-ROW", Token.KEYWORD1);
			progKeywords.add("POPUP-MENU", Token.KEYWORD1);
			progKeywords.add("POPUP-ONLY", Token.KEYWORD1);
			progKeywords.add("PORTRAIT", Token.KEYWORD1);
			progKeywords.add("POSITION", Token.KEYWORD1);
			progKeywords.add("PRECISION", Token.KEYWORD1);
			progKeywords.add("PREPARE-STRING", Token.KEYWORD1);
			progKeywords.add("PREPARED", Token.KEYWORD1);
			progKeywords.add("PREPROCESS", Token.KEYWORD1);
			progKeywords.add("PRESELECT", Token.KEYWORD1);
			progKeywords.add("PREV", Token.KEYWORD1);
			progKeywords.add("PREV-COLUMN", Token.KEYWORD1);
			progKeywords.add("PREV-FRAME", Token.KEYWORD1);
			progKeywords.add("PREV-SIBLING", Token.KEYWORD1);
			progKeywords.add("PREV-TAB-ITEM", Token.KEYWORD1);
			progKeywords.add("PREV-WORD", Token.KEYWORD1);
			progKeywords.add("PRIMARY", Token.KEYWORD1);
			progKeywords.add("PRINTER", Token.KEYWORD1);
			progKeywords.add("PRINTER-CONTROL-HANDLE", Token.KEYWORD1);
			progKeywords.add("PRINTER-HDC", Token.KEYWORD1);
			progKeywords.add("PRINTER-NAME", Token.KEYWORD1);
			progKeywords.add("PRINTER-PORT", Token.KEYWORD1);
			progKeywords.add("PRINTER-SETUP", Token.KEYWORD1);
			progKeywords.add("PRIVATE", Token.KEYWORD1);
			progKeywords.add("PRIVATE-DATA", Token.KEYWORD1);
			progKeywords.add("PRIVILEGES", Token.KEYWORD1);
			progKeywords.add("PROC-HANDLE", Token.KEYWORD1);
			progKeywords.add("PROC-STATUS", Token.KEYWORD1);
			progKeywords.add("PROCEDURE", Token.KEYWORD1);
			progKeywords.add("PROCEDURE-COMPLETE", Token.KEYWORD1);
			progKeywords.add("PROCEDURE-NAME", Token.KEYWORD1);
			progKeywords.add("PROCESS", Token.KEYWORD1);
			progKeywords.add("PROFILE-FILE", Token.KEYWORD1);
			progKeywords.add("PROFILER", Token.KEYWORD1);
			progKeywords.add("PROFILING", Token.KEYWORD1);
			progKeywords.add("PROGRAM-NAME", Token.KEYWORD1);
			progKeywords.add("PROGRESS", Token.KEYWORD1);
			progKeywords.add("PROGRESS-SOURCE", Token.KEYWORD1);
			progKeywords.add("PROMPT", Token.KEYWORD1);
			progKeywords.add("PROMPT-FOR", Token.KEYWORD1);
			progKeywords.add("PROMSGS", Token.KEYWORD1);
			progKeywords.add("PROPATH", Token.KEYWORD1);
			progKeywords.add("PROVERSION", Token.KEYWORD1);
			progKeywords.add("PROXY", Token.KEYWORD1);
			progKeywords.add("PUBLIC-ID", Token.KEYWORD1);
			progKeywords.add("PUBLISH", Token.KEYWORD1);
			progKeywords.add("PUBLISHED-EVENTS", Token.KEYWORD1);
			progKeywords.add("PUT", Token.KEYWORD1);
			progKeywords.add("PUT-BITS", Token.KEYWORD1);
			progKeywords.add("PUT-BYTE", Token.KEYWORD1);
			progKeywords.add("PUT-BYTES", Token.KEYWORD1);
			progKeywords.add("PUT-DOUBLE", Token.KEYWORD1);
			progKeywords.add("PUT-FLOAT", Token.KEYWORD1);
			progKeywords.add("PUT-KEY-VALUE", Token.KEYWORD1);
			progKeywords.add("PUT-LONG", Token.KEYWORD1);
			progKeywords.add("PUT-SHORT", Token.KEYWORD1);
			progKeywords.add("PUT-STRING", Token.KEYWORD1);
			progKeywords.add("PUT-UNSIGNED-SHORT", Token.KEYWORD1);
			progKeywords.add("PUTBYTE", Token.KEYWORD1);
			progKeywords.add("QUERY", Token.KEYWORD1);
			progKeywords.add("QUERY-CLOSE", Token.KEYWORD1);
			progKeywords.add("QUERY-OFF-END", Token.KEYWORD1);
			progKeywords.add("QUERY-OPEN", Token.KEYWORD1);
			progKeywords.add("QUERY-PREPARE", Token.KEYWORD1);
			progKeywords.add("QUERY-TUNING", Token.KEYWORD1);
			progKeywords.add("QUESTION", Token.KEYWORD1);
			progKeywords.add("QUIT", Token.KEYWORD1);
			progKeywords.add("R-INDEX", Token.KEYWORD1);
			progKeywords.add("RADIO-BUTTONS", Token.KEYWORD1);
			progKeywords.add("RADIO-SET", Token.KEYWORD1);
			progKeywords.add("RANDOM", Token.KEYWORD1);
			progKeywords.add("RAW", Token.KEYWORD1);
			progKeywords.add("RAW-TRANSFER", Token.KEYWORD1);
			progKeywords.add("RCODE-INFORMATION", Token.KEYWORD1);
			progKeywords.add("READ", Token.KEYWORD1);
			progKeywords.add("READ-AVAILABLE", Token.KEYWORD1);
			progKeywords.add("READ-EXACT-NUM", Token.KEYWORD1);
			progKeywords.add("READ-FILE", Token.KEYWORD1);
			progKeywords.add("READ-ONLY", Token.KEYWORD1);
			progKeywords.add("READ-RESPONSE", Token.KEYWORD1);
			progKeywords.add("READKEY", Token.KEYWORD1);
			progKeywords.add("REAL", Token.KEYWORD1);
			progKeywords.add("RECALL", Token.KEYWORD1);
			progKeywords.add("RECID", Token.KEYWORD1);
			progKeywords.add("RECORD-LENGTH", Token.KEYWORD1);
			progKeywords.add("RECTANGLE", Token.KEYWORD1);
			progKeywords.add("RECURSIVE", Token.KEYWORD1);
			progKeywords.add("REFRESH", Token.KEYWORD1);
			progKeywords.add("REFRESHABLE", Token.KEYWORD1);
			progKeywords.add("RELEASE", Token.KEYWORD1);
			progKeywords.add("REMOTE", Token.KEYWORD1);
			progKeywords.add("REMOTE-HOST", Token.KEYWORD1);
			progKeywords.add("REMOTE-PORT", Token.KEYWORD1);
			progKeywords.add("REMOVE-ATTRIBUTE", Token.KEYWORD1);
			progKeywords.add("REMOVE-CHILD", Token.KEYWORD1);
			progKeywords.add("REMOVE-EVENTS-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("REMOVE-SUPER-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("REPEAT", Token.KEYWORD1);
			progKeywords.add("REPLACE", Token.KEYWORD1);
			progKeywords.add("REPLACE-CHILD", Token.KEYWORD1);
			progKeywords.add("REPLACE-SELECTION-TEXT", Token.KEYWORD1);
			progKeywords.add("REPLICATION-CREATE", Token.KEYWORD1);
			progKeywords.add("REPLICATION-DELETE", Token.KEYWORD1);
			progKeywords.add("REPLICATION-WRITE", Token.KEYWORD1);
			progKeywords.add("REPORTS", Token.KEYWORD1);
			progKeywords.add("REPOSITION", Token.KEYWORD1);
			progKeywords.add("REPOSITION-BACKWARDS", Token.KEYWORD1);
			progKeywords.add("REPOSITION-FORWARDS", Token.KEYWORD1);
			progKeywords.add("REPOSITION-TO-ROW", Token.KEYWORD1);
			progKeywords.add("REPOSITION-TO-ROWID", Token.KEYWORD1);
			progKeywords.add("REQUEST", Token.KEYWORD1);
			progKeywords.add("RESIZABLE", Token.KEYWORD1);
			progKeywords.add("RESIZE", Token.KEYWORD1);
			progKeywords.add("RESULT", Token.KEYWORD1);
			progKeywords.add("RESUME-DISPLAY", Token.KEYWORD1);
			progKeywords.add("RETAIN", Token.KEYWORD1);
			progKeywords.add("RETAIN-SHAPE", Token.KEYWORD1);
			progKeywords.add("RETRY", Token.KEYWORD1);
			progKeywords.add("RETRY-CANCEL", Token.KEYWORD1);
			progKeywords.add("RETURN", Token.KEYWORD1);
			progKeywords.add("RETURN-INSERTED", Token.KEYWORD1);
			progKeywords.add("RETURN-TO-START-DIR", Token.KEYWORD1);
			progKeywords.add("RETURN-VALUE", Token.KEYWORD1);
			progKeywords.add("RETURNS", Token.KEYWORD1);
			progKeywords.add("REVERSE-FROM", Token.KEYWORD1);
			progKeywords.add("REVERT", Token.KEYWORD1);
			progKeywords.add("REVOKE", Token.KEYWORD1);
			progKeywords.add("RGB-VALUE", Token.KEYWORD1);
			progKeywords.add("RIGHT", Token.KEYWORD1);
			progKeywords.add("RIGHT-ALIGNED", Token.KEYWORD1);
			progKeywords.add("RIGHT-END", Token.KEYWORD1);
			progKeywords.add("RIGHT-TRIM", Token.KEYWORD1);
			progKeywords.add("ROUND", Token.KEYWORD1);
			progKeywords.add("ROW", Token.KEYWORD1);
			progKeywords.add("ROW-DISPLAY", Token.KEYWORD1);
			progKeywords.add("ROW-ENTRY", Token.KEYWORD1);
			progKeywords.add("ROW-HEIGHT", Token.KEYWORD1);
			progKeywords.add("ROW-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("ROW-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("ROW-LEAVE", Token.KEYWORD1);
			progKeywords.add("ROW-MARKERS", Token.KEYWORD1);
			progKeywords.add("ROW-OF", Token.KEYWORD1);
			progKeywords.add("ROW-RESIZABLE", Token.KEYWORD1);
			progKeywords.add("ROWID", Token.KEYWORD1);
			progKeywords.add("RULE", Token.KEYWORD1);
			progKeywords.add("RULE-ROW", Token.KEYWORD1);
			progKeywords.add("RULE-Y", Token.KEYWORD1);
			progKeywords.add("RUN", Token.KEYWORD1);
			progKeywords.add("RUN-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("SAVE", Token.KEYWORD1);
			progKeywords.add("SAVE-AS", Token.KEYWORD1);
			progKeywords.add("SAVE-FILE", Token.KEYWORD1);
			progKeywords.add("SAX-XML", Token.KEYWORD1);
			progKeywords.add("SCHEMA", Token.KEYWORD1);
			progKeywords.add("SCREEN", Token.KEYWORD1);
			progKeywords.add("SCREEN-IO", Token.KEYWORD1);
			progKeywords.add("SCREEN-LINES", Token.KEYWORD1);
			progKeywords.add("SCREEN-VALUE", Token.KEYWORD1);
			progKeywords.add("SCROLL", Token.KEYWORD1);
			progKeywords.add("SCROLL-BARS", Token.KEYWORD1);
			progKeywords.add("SCROLL-LEFT", Token.KEYWORD1);
			progKeywords.add("SCROLL-MODE", Token.KEYWORD1);
			progKeywords.add("SCROLL-NOTIFY", Token.KEYWORD1);
			progKeywords.add("SCROLL-RIGHT", Token.KEYWORD1);
			progKeywords.add("SCROLL-TO-CURRENT-ROW", Token.KEYWORD1);
			progKeywords.add("SCROLL-TO-ITEM", Token.KEYWORD1);
			progKeywords.add("SCROLL-TO-SELECTED-ROW", Token.KEYWORD1);
			progKeywords.add("SCROLLABLE", Token.KEYWORD1);
			progKeywords.add("SCROLLBAR-DRAG", Token.KEYWORD1);
			progKeywords.add("SCROLLBAR-HORIZONTAL", Token.KEYWORD1);
			progKeywords.add("SCROLLBAR-VERTICAL", Token.KEYWORD1);
			progKeywords.add("SCROLLED-ROW-POSITION", Token.KEYWORD1);
			progKeywords.add("SCROLLING", Token.KEYWORD1);
			progKeywords.add("SDBNAME", Token.KEYWORD1);
			progKeywords.add("SEARCH", Token.KEYWORD1);
			progKeywords.add("SEARCH-SELF", Token.KEYWORD1);
			progKeywords.add("SEARCH-TARGET", Token.KEYWORD1);
			progKeywords.add("SECTION", Token.KEYWORD1);
			progKeywords.add("SEEK", Token.KEYWORD1);
			progKeywords.add("SELECT", Token.KEYWORD1);
			progKeywords.add("SELECT-ALL", Token.KEYWORD1);
			progKeywords.add("SELECT-EXTEND", Token.KEYWORD1);
			progKeywords.add("SELECT-FOCUSED-ROW", Token.KEYWORD1);
			progKeywords.add("SELECT-NEXT-ROW", Token.KEYWORD1);
			progKeywords.add("SELECT-PREV-ROW", Token.KEYWORD1);
			progKeywords.add("SELECT-REPOSITIONED-ROW", Token.KEYWORD1);
			progKeywords.add("SELECT-ROW", Token.KEYWORD1);
			progKeywords.add("SELECTABLE", Token.KEYWORD1);
			progKeywords.add("SELECTED", Token.KEYWORD1);
			progKeywords.add("SELECTED-ITEMS", Token.KEYWORD1);
			progKeywords.add("SELECTION", Token.KEYWORD1);
			progKeywords.add("SELECTION-END", Token.KEYWORD1);
			progKeywords.add("SELECTION-EXTEND", Token.KEYWORD1);
			progKeywords.add("SELECTION-LIST", Token.KEYWORD1);
			progKeywords.add("SELECTION-START", Token.KEYWORD1);
			progKeywords.add("SELECTION-TEXT", Token.KEYWORD1);
			progKeywords.add("SELF", Token.KEYWORD1);
			progKeywords.add("SEND", Token.KEYWORD1);
			progKeywords.add("SENSITIVE", Token.KEYWORD1);
			progKeywords.add("SEPARATE-CONNECTION", Token.KEYWORD1);
			progKeywords.add("SEPARATOR-FGCOLOR", Token.KEYWORD1);
			progKeywords.add("SEPARATORS", Token.KEYWORD1);
			progKeywords.add("SERVER", Token.KEYWORD1);
			progKeywords.add("SERVER-CONNECTION-BOUND", Token.KEYWORD1);
			progKeywords.add("SERVER-CONNECTION-BOUND-REQUEST", Token.KEYWORD1);
			progKeywords.add("SERVER-CONNECTION-CONTEXT", Token.KEYWORD1);
			progKeywords.add("SERVER-CONNECTION-ID", Token.KEYWORD1);
			progKeywords.add("SERVER-OPERATING-MODE", Token.KEYWORD1);
			progKeywords.add("SERVER-SOCKET", Token.KEYWORD1);
			progKeywords.add("SESSION", Token.KEYWORD1);
			progKeywords.add("SESSION-END", Token.KEYWORD1);
			progKeywords.add("SET", Token.KEYWORD2);
			progKeywords.add("SET-ATTRIBUTE", Token.KEYWORD2);
			progKeywords.add("SET-ATTRIBUTE-NODE", Token.KEYWORD2);
			progKeywords.add("SET-BLUE-VALUE", Token.KEYWORD2);
			progKeywords.add("SET-BREAK", Token.KEYWORD2);
			progKeywords.add("SET-BUFFERS", Token.KEYWORD2);
			progKeywords.add("SET-BYTE-ORDER", Token.KEYWORD2);
			progKeywords.add("SET-CELL-FOCUS", Token.KEYWORD2);
			progKeywords.add("SET-COMMIT", Token.KEYWORD2);
			progKeywords.add("SET-CONNECT-PROCEDURE", Token.KEYWORD2);
			progKeywords.add("SET-CONTENTS", Token.KEYWORD2);
			progKeywords.add("SET-DYNAMIC", Token.KEYWORD2);
			progKeywords.add("SET-GREEN-VALUE", Token.KEYWORD2);
			progKeywords.add("SET-NUMERIC-FORMAT", Token.KEYWORD2);
			progKeywords.add("SET-POINTER-VALUE", Token.KEYWORD2);
			progKeywords.add("SET-READ-RESPONSE-PROCEDURE", Token.KEYWORD2);
			progKeywords.add("SET-RED-VALUE", Token.KEYWORD2);
			progKeywords.add("SET-REPOSITIONED-ROW", Token.KEYWORD2);
			progKeywords.add("SET-RGB-VALUE", Token.KEYWORD2);
			progKeywords.add("SET-ROLLBACK", Token.KEYWORD2);
			progKeywords.add("SET-SELECTION", Token.KEYWORD2);
			progKeywords.add("SET-SIZE", Token.KEYWORD2);
			progKeywords.add("SET-SOCKET-OPTION", Token.KEYWORD2);
			progKeywords.add("SET-WAIT-STATE", Token.KEYWORD2);
			progKeywords.add("SETTINGS", Token.KEYWORD1);
			progKeywords.add("SETUSERID", Token.KEYWORD1);
			progKeywords.add("SHARE-LOCK", Token.KEYWORD1);
			progKeywords.add("SHARED", Token.KEYWORD1);
			progKeywords.add("SHORT", Token.KEYWORD1);
			progKeywords.add("SHOW-IN-TASKBAR", Token.KEYWORD1);
			progKeywords.add("SHOW-STATS", Token.KEYWORD1);
			progKeywords.add("SIDE-LABEL", Token.KEYWORD1);
			progKeywords.add("SIDE-LABEL-HANDLE", Token.KEYWORD1);
			progKeywords.add("SIDE-LABELS", Token.KEYWORD1);
			progKeywords.add("SILENT", Token.KEYWORD1);
			progKeywords.add("SIMPLE", Token.KEYWORD1);
			progKeywords.add("SINGLE", Token.KEYWORD1);
			progKeywords.add("SIZE", Token.KEYWORD1);
			progKeywords.add("SIZE-CHARS", Token.KEYWORD1);
			progKeywords.add("SIZE-PIXELS", Token.KEYWORD1);
			progKeywords.add("SKIP", Token.KEYWORD1);
			progKeywords.add("SKIP-DELETED-RECORD", Token.KEYWORD1);
			progKeywords.add("SKIP-SCHEMA-CHECK", Token.KEYWORD1);
			progKeywords.add("SLIDER", Token.KEYWORD1);
			progKeywords.add("SMALL-ICON", Token.KEYWORD1);
			progKeywords.add("SMALL-TITLE", Token.KEYWORD1);
			progKeywords.add("SMALLINT", Token.KEYWORD1);
			progKeywords.add("SOCKET", Token.KEYWORD1);
			progKeywords.add("SOME", Token.KEYWORD1);
			progKeywords.add("SORT", Token.KEYWORD1);
			progKeywords.add("SOURCE", Token.KEYWORD1);
			progKeywords.add("SOURCE-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("SPACE", Token.KEYWORD1);
			progKeywords.add("SQL", Token.KEYWORD1);
			progKeywords.add("SQRT", Token.KEYWORD1);
			progKeywords.add("START", Token.KEYWORD1);
			progKeywords.add("START-BOX-SELECTION", Token.KEYWORD1);
			progKeywords.add("START-EXTEND-BOX-SELECTION", Token.KEYWORD1);
			progKeywords.add("START-MOVE", Token.KEYWORD1);
			progKeywords.add("START-RESIZE", Token.KEYWORD1);
			progKeywords.add("START-ROW-RESIZE", Token.KEYWORD1);
			progKeywords.add("START-SEARCH", Token.KEYWORD1);
			progKeywords.add("STATUS", Token.KEYWORD1);
			progKeywords.add("STATUS-AREA", Token.KEYWORD1);
			progKeywords.add("STATUS-AREA-FONT", Token.KEYWORD1);
			progKeywords.add("STDCALL", Token.KEYWORD1);
			progKeywords.add("STOP", Token.KEYWORD1);
			progKeywords.add("STOP-DISPLAY", Token.KEYWORD1);
			progKeywords.add("STOPPED", Token.KEYWORD1);
			progKeywords.add("STORED-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("STREAM", Token.KEYWORD1);
			progKeywords.add("STREAM-IO", Token.KEYWORD1);
			progKeywords.add("STRETCH-TO-FIT", Token.KEYWORD1);
			progKeywords.add("STRING", Token.KEYWORD1);
			progKeywords.add("STRING-VALUE", Token.KEYWORD1);
			progKeywords.add("STRING-XREF", Token.KEYWORD1);
			progKeywords.add("SUB-AVERAGE", Token.KEYWORD1);
			progKeywords.add("SUB-COUNT", Token.KEYWORD1);
			progKeywords.add("SUB-MAXIMUM", Token.KEYWORD1);
			progKeywords.add("SUB-MENU", Token.KEYWORD1);
			progKeywords.add("SUB-MENU-HELP", Token.KEYWORD1);
			progKeywords.add("SUB-MINIMUM", Token.KEYWORD1);
			progKeywords.add("SUB-TOTAL", Token.KEYWORD1);
			progKeywords.add("SUBSCRIBE", Token.KEYWORD1);
			progKeywords.add("SUBSTITUTE", Token.KEYWORD1);
			progKeywords.add("SUBSTRING", Token.KEYWORD1);
			progKeywords.add("SUBTYPE", Token.KEYWORD1);
			progKeywords.add("SUM", Token.KEYWORD1);
			progKeywords.add("SUMMARY", Token.KEYWORD1);
			progKeywords.add("SUPER", Token.KEYWORD1);
			progKeywords.add("SUPER-PROCEDURES", Token.KEYWORD1);
			progKeywords.add("SUPPRESS-WARNINGS", Token.KEYWORD1);
			progKeywords.add("SYSTEM-ALERT-BOXES", Token.KEYWORD1);
			progKeywords.add("SYSTEM-DIALOG", Token.KEYWORD1);
			progKeywords.add("SYSTEM-HELP", Token.KEYWORD1);
			progKeywords.add("SYSTEM-ID", Token.KEYWORD1);
			progKeywords.add("TAB", Token.KEYWORD1);
			progKeywords.add("TAB-POSITION", Token.KEYWORD1);
			progKeywords.add("TAB-STOP", Token.KEYWORD1);
			progKeywords.add("TABLE", Token.KEYWORD1);
			progKeywords.add("TABLE-HANDLE", Token.KEYWORD1);
			progKeywords.add("TABLE-NUMBER", Token.KEYWORD1);
			progKeywords.add("TARGET", Token.KEYWORD1);
			progKeywords.add("TARGET-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("TEMP-DIRECTORY", Token.KEYWORD1);
			progKeywords.add("TEMP-TABLE", Token.KEYWORD1);
			progKeywords.add("TEMP-TABLE-PREPARE", Token.KEYWORD1);
			progKeywords.add("TERM", Token.KEYWORD1);
			progKeywords.add("TERMINAL", Token.KEYWORD1);
			progKeywords.add("TERMINATE", Token.KEYWORD1);
			progKeywords.add("TEXT", Token.KEYWORD1);
			progKeywords.add("TEXT-CURSOR", Token.KEYWORD1);
			progKeywords.add("TEXT-SEG-GROWTH", Token.KEYWORD1);
			progKeywords.add("TEXT-SELECTED", Token.KEYWORD1);
			progKeywords.add("THEN", Token.KEYWORD1);
			progKeywords.add("THIS-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("THREE-D", Token.KEYWORD1);
			progKeywords.add("THROUGH", Token.KEYWORD1);
			progKeywords.add("THRU", Token.KEYWORD1);
			progKeywords.add("TIC-MARKS", Token.KEYWORD1);
			progKeywords.add("TIME", Token.KEYWORD1);
			progKeywords.add("TIME-SOURCE", Token.KEYWORD1);
			progKeywords.add("TITLE", Token.KEYWORD1);
			progKeywords.add("TITLE-BGCOLOR", Token.KEYWORD1);
			progKeywords.add("TITLE-DCOLOR", Token.KEYWORD1);
			progKeywords.add("TITLE-FGCOLOR", Token.KEYWORD1);
			progKeywords.add("TITLE-FONT", Token.KEYWORD1);
			progKeywords.add("TO", Token.KEYWORD1);
			progKeywords.add("TO-ROWID", Token.KEYWORD1);
			progKeywords.add("TODAY", Token.KEYWORD1);
			progKeywords.add("TOGGLE-BOX", Token.KEYWORD1);
			progKeywords.add("TOOLTIP", Token.KEYWORD1);
			progKeywords.add("TOOLTIPS", Token.KEYWORD1);
			progKeywords.add("TOP", Token.KEYWORD1);
			progKeywords.add("TOP-COLUMN", Token.KEYWORD1);
			progKeywords.add("TOP-ONLY", Token.KEYWORD1);
			progKeywords.add("TOPIC", Token.KEYWORD1);
			progKeywords.add("TOTAL", Token.KEYWORD1);
			progKeywords.add("TRACE-FILTER", Token.KEYWORD1);
			progKeywords.add("TRACING", Token.KEYWORD1);
			progKeywords.add("TRAILING", Token.KEYWORD1);
			progKeywords.add("TRANS", Token.KEYWORD1);
			progKeywords.add("TRANS-INIT-PROCEDURE", Token.KEYWORD1);
			progKeywords.add("TRANSACTION", Token.KEYWORD1);
			progKeywords.add("TRANSACTION-MODE", Token.KEYWORD1);
			progKeywords.add("TRANSPARENT", Token.KEYWORD1);
			progKeywords.add("TRIGGER", Token.KEYWORD1);
			progKeywords.add("TRIGGERS", Token.KEYWORD1);
			progKeywords.add("TRIM", Token.KEYWORD1);
			progKeywords.add("TRUE", Token.LITERAL2);
			progKeywords.add("TRUNCATE", Token.KEYWORD1);
			progKeywords.add("TYPE", Token.KEYWORD1);
			progKeywords.add("UNBUFFERED", Token.KEYWORD1);
			progKeywords.add("UNDERLINE", Token.KEYWORD1);
			progKeywords.add("UNDO", Token.KEYWORD1);
			progKeywords.add("UNFORMATTED", Token.KEYWORD1);
			progKeywords.add("UNION", Token.KEYWORD1);
			progKeywords.add("UNIQUE", Token.KEYWORD1);
			progKeywords.add("UNIQUE-ID", Token.KEYWORD1);
			progKeywords.add("UNIQUE-MATCH", Token.KEYWORD1);
			progKeywords.add("UNIX", Token.KEYWORD1);
			progKeywords.add("UNIX-END", Token.KEYWORD1);
			progKeywords.add("UNLESS-HIDDEN", Token.KEYWORD1);
			progKeywords.add("UNLOAD", Token.KEYWORD1);
			progKeywords.add("UNSIGNED-SHORT", Token.KEYWORD1);
			progKeywords.add("UNSUBSCRIBE", Token.KEYWORD1);
			progKeywords.add("UP", Token.KEYWORD1);
			progKeywords.add("UPDATE", Token.KEYWORD1);
			progKeywords.add("UPPER", Token.KEYWORD1);
			progKeywords.add("URL", Token.KEYWORD1);
			progKeywords.add("URL-DECODE", Token.KEYWORD1);
			progKeywords.add("URL-ENCODE", Token.KEYWORD1);
			progKeywords.add("URL-PASSWORD", Token.KEYWORD1);
			progKeywords.add("URL-USERID", Token.KEYWORD1);
			progKeywords.add("USE", Token.KEYWORD1);
			progKeywords.add("USE-DICT-EXPS", Token.KEYWORD1);
			progKeywords.add("USE-FILENAME", Token.KEYWORD1);
			progKeywords.add("USE-INDEX", Token.KEYWORD1);
			progKeywords.add("USE-REVVIDEO", Token.KEYWORD1);
			progKeywords.add("USE-TEXT", Token.KEYWORD1);
			progKeywords.add("USE-UNDERLINE", Token.KEYWORD1);
			progKeywords.add("USER", Token.KEYWORD1);
			progKeywords.add("USER-DATA", Token.KEYWORD1);
			progKeywords.add("USERID", Token.KEYWORD1);
			progKeywords.add("USING", Token.KEYWORD1);
			progKeywords.add("UTC-OFFSET", Token.KEYWORD1);
			progKeywords.add("V6DISPLAY", Token.KEYWORD1);
			progKeywords.add("V6FRAME", Token.KEYWORD1);
			progKeywords.add("VALID-EVENT", Token.KEYWORD1);
			progKeywords.add("VALID-HANDLE", Token.KEYWORD1);
			progKeywords.add("VALIDATE", Token.KEYWORD1);
			progKeywords.add("VALIDATE-EXPRESSION", Token.KEYWORD1);
			progKeywords.add("VALIDATE-MESSAGE", Token.KEYWORD1);
			progKeywords.add("VALIDATE-XML", Token.KEYWORD1);
			progKeywords.add("VALUE", Token.KEYWORD1);
			progKeywords.add("VALUE-CHANGED", Token.KEYWORD1);
			progKeywords.add("VALUES", Token.KEYWORD1);
			progKeywords.add("VARIABLE", Token.KEYWORD1);
			progKeywords.add("VERBOSE", Token.KEYWORD1);
			progKeywords.add("VERTICAL", Token.KEYWORD1);
			progKeywords.add("VIEW", Token.KEYWORD1);
			progKeywords.add("VIEW-AS", Token.KEYWORD1);
			progKeywords.add("VIRTUAL-HEIGHT", Token.KEYWORD1);
			progKeywords.add("VIRTUAL-HEIGHT-CHARS", Token.KEYWORD1);
			progKeywords.add("VIRTUAL-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("VIRTUAL-WIDTH", Token.KEYWORD1);
			progKeywords.add("VIRTUAL-WIDTH-CHARS", Token.KEYWORD1);
			progKeywords.add("VIRTUAL-WIDTH-PIXELS", Token.KEYWORD1);
			progKeywords.add("VISIBLE", Token.KEYWORD1);
			progKeywords.add("VMS", Token.KEYWORD1);
			progKeywords.add("WAIT", Token.KEYWORD1);
			progKeywords.add("WAIT-FOR", Token.KEYWORD1);
			progKeywords.add("WARNING", Token.KEYWORD1);
			progKeywords.add("WEB-CONTEXT", Token.KEYWORD1);
			progKeywords.add("WEB-NOTIFY", Token.KEYWORD1);
			progKeywords.add("WEEKDAY", Token.KEYWORD1);
			progKeywords.add("WHEN", Token.KEYWORD1);
			progKeywords.add("WHERE", Token.KEYWORD1);
			progKeywords.add("WHILE", Token.KEYWORD1);
			progKeywords.add("WIDGET", Token.KEYWORD1);
			progKeywords.add("WIDGET-ENTER", Token.KEYWORD1);
			progKeywords.add("WIDGET-HANDLE", Token.KEYWORD1);
			progKeywords.add("WIDGET-LEAVE", Token.KEYWORD1);
			progKeywords.add("WIDGET-POOL", Token.KEYWORD1);
			progKeywords.add("WIDTH", Token.KEYWORD1);
			progKeywords.add("WIDTH-CHARS", Token.KEYWORD1);
			progKeywords.add("WIDTH-PIXELS", Token.KEYWORD1);
			progKeywords.add("WINDOW", Token.KEYWORD1);
			progKeywords.add("WINDOW-CLOSE", Token.KEYWORD1);
			progKeywords.add("WINDOW-DELAYED-MINIMIZE", Token.KEYWORD1);
			progKeywords.add("WINDOW-MAXIMIZED", Token.KEYWORD1);
			progKeywords.add("WINDOW-MAXIMIZED", Token.KEYWORD1);
			progKeywords.add("WINDOW-MINIMIZED", Token.KEYWORD1);
			progKeywords.add("WINDOW-MINIMIZED", Token.KEYWORD1);
			progKeywords.add("WINDOW-NAME", Token.KEYWORD1);
			progKeywords.add("WINDOW-NORMAL", Token.KEYWORD1);
			progKeywords.add("WINDOW-RESIZED", Token.KEYWORD1);
			progKeywords.add("WINDOW-RESTORED", Token.KEYWORD1);
			progKeywords.add("WINDOW-STATE", Token.KEYWORD1);
			progKeywords.add("WINDOW-SYSTEM", Token.KEYWORD1);
			progKeywords.add("WITH", Token.KEYWORD1);
			progKeywords.add("WORD-INDEX", Token.KEYWORD1);
			progKeywords.add("WORD-WRAP", Token.KEYWORD1);
			progKeywords.add("WORK-AREA-HEIGHT-PIXELS", Token.KEYWORD1);
			progKeywords.add("WORK-AREA-WIDTH-PIXELS", Token.KEYWORD1);
			progKeywords.add("WORK-AREA-X", Token.KEYWORD1);
			progKeywords.add("WORK-AREA-Y", Token.KEYWORD1);
			progKeywords.add("WORK-TABLE", Token.KEYWORD1);
			progKeywords.add("WORKFILE", Token.KEYWORD1);
			progKeywords.add("WRITE", Token.KEYWORD1);
			progKeywords.add("WRITE-DATA", Token.KEYWORD1);
			progKeywords.add("X", Token.KEYWORD1);
			progKeywords.add("X-DOCUMENT", Token.KEYWORD1);
			progKeywords.add("X-NODEREF", Token.KEYWORD1);
			progKeywords.add("X-OF", Token.KEYWORD1);
			progKeywords.add("XCODE", Token.KEYWORD1);
			progKeywords.add("XREF", Token.KEYWORD1);
			progKeywords.add("Y", Token.KEYWORD1);
			progKeywords.add("Y-OF", Token.KEYWORD1);
			progKeywords.add("YEAR", Token.KEYWORD1);
			progKeywords.add("YEAR-OFFSET", Token.KEYWORD1);
			progKeywords.add("YES", Token.KEYWORD1);
			progKeywords.add("YES-NO", Token.KEYWORD1);
			progKeywords.add("YES-NO-CANCEL", Token.KEYWORD1);
			progKeywords.add("&ANALYZE-RESUME", Token.KEYWORD2);
			progKeywords.add("&ANALYZE-SUSPEND", Token.KEYWORD2);
			progKeywords.add("&ELSE", Token.KEYWORD2);
			progKeywords.add("&ELSEIF", Token.KEYWORD2);
			progKeywords.add("&ENDIF", Token.KEYWORD2);
			progKeywords.add("&FILE-NAME", Token.KEYWORD2);
			progKeywords.add("pp&GLOBAL", Token.KEYWORD2);
			progKeywords.add("&GLOBAL-DEFINE", Token.KEYWORD2);
			progKeywords.add("&IF", Token.KEYWORD2);
			progKeywords.add("&MESSAGE", Token.KEYWORD2);
			progKeywords.add("&OPSYS", Token.KEYWORD2);
			progKeywords.add("&SCOPED", Token.KEYWORD2);
			progKeywords.add("&SCOPED-DEFINE", Token.KEYWORD2);
			progKeywords.add("pp&THEN", Token.KEYWORD2);
			progKeywords.add("&UNDEFINE", Token.KEYWORD2);
			progKeywords.add("{&BATCH-MODE}", Token.KEYWORD2);
			progKeywords.add("{&FILE-NAME}", Token.KEYWORD2);
			progKeywords.add("{&LINE-NUMBER}", Token.KEYWORD2);
			progKeywords.add("{&OPSYS}", Token.KEYWORD2);
			progKeywords.add("{&SEQUENCE}", Token.KEYWORD2);
			progKeywords.add("{&WINDOW-SYSTEM}", Token.KEYWORD2);
			progKeywords.add("&", Token.KEYWORD3);
			progKeywords.add("(", Token.KEYWORD3);
			progKeywords.add(") ", Token.KEYWORD3);
			progKeywords.add("* ", Token.KEYWORD3);
			progKeywords.add("+ ", Token.KEYWORD3);
			progKeywords.add(", ", Token.KEYWORD3);
			progKeywords.add("- ", Token.KEYWORD3);
			progKeywords.add(". ", Token.KEYWORD3);
			progKeywords.add("/ ", Token.KEYWORD3);
			progKeywords.add(": ", Token.KEYWORD3);
			progKeywords.add("; ", Token.KEYWORD3);
			progKeywords.add("< ", Token.KEYWORD3);
			progKeywords.add("<=", Token.KEYWORD3);
			progKeywords.add("<>", Token.KEYWORD3);
			progKeywords.add("= ", Token.KEYWORD3);
			progKeywords.add(">", Token.KEYWORD3);
			progKeywords.add(">=", Token.KEYWORD3);
			progKeywords.add("?", Token.KEYWORD3);
			progKeywords.add("@", Token.KEYWORD3);
			progKeywords.add("[", Token.KEYWORD3);
			progKeywords.add("]", Token.KEYWORD3);
			progKeywords.add("^", Token.KEYWORD3);
			progKeywords.add("{", Token.KEYWORD3);
			progKeywords.add("{get ", Token.KEYWORD3);
			progKeywords.add("{set ", Token.KEYWORD3);
			progKeywords.add("} ", Token.KEYWORD3);
			progKeywords.add("~", Token.KEYWORD3);

		}
		return progKeywords;
	}

	// private members
	private static KeywordMap progKeywords;

	private boolean cpp;
	private boolean javadoc;
	private KeywordMap keywords;
	private int lastOffset;
	private int lastKeyword;

	private boolean doKeyword(Segment line, int i, char c) {
		int i1 = i + 1;

		int len = i - lastKeyword;
		byte id = keywords.lookup(line, lastKeyword, len);
		if (id != Token.NULL) {
			if (lastKeyword != lastOffset)
				addToken(lastKeyword - lastOffset, Token.NULL);
			addToken(len, id);
			lastOffset = i;
		}
		lastKeyword = i1;
		return false;
	}
}

/*
 * ChangeLog: $Log: ProgressTokenMarker.java,v $ Revision 1.35 2000/01/29
 * 10:12:43 sp BeanShell edit mode, bug fixes
 * 
 * Revision 1.34 1999/12/13 03:40:29 sp Bug fixes, syntax is now mostly GPL'd
 * 
 * Revision 1.33 1999/10/31 07:15:34 sp New logging API, splash screen updates,
 * bug fixes
 * 
 * Revision 1.32 1999/09/30 12:21:04 sp No net access for a month... so here's
 * one big jEdit 2.1pre1
 * 
 * Revision 1.31 1999/08/21 01:48:18 sp jEdit 2.0pre8
 * 
 * Revision 1.30 1999/06/05 00:22:58 sp LGPL'd syntax package
 * 
 * Revision 1.29 1999/06/03 08:24:13 sp Fixing broken CVS
 * 
 * Revision 1.30 1999/05/31 08:11:10 sp Syntax coloring updates, expand abbrev
 * bug fix
 * 
 * Revision 1.29 1999/05/31 04:38:51 sp Syntax optimizations, HyperSearch for
 * Selection added (Mike Dillon)
 * 
 * Revision 1.28 1999/05/29 03:46:53 sp ProgressTokenMarker bug fix, new splash
 * screen
 * 
 * Revision 1.27 1999/05/14 04:56:15 sp Docs updated, default: fix in C/C++/Java
 * mode, full path in title bar toggle
 * 
 * Revision 1.26 1999/05/11 09:05:10 sp New version1.6.html file, some other
 * stuff perhaps
 * 
 * Revision 1.25 1999/04/22 06:03:26 sp Syntax colorizing change
 * 
 * Revision 1.24 1999/04/19 05:38:20 sp Syntax API changes
 * 
 * Revision 1.23 1999/03/13 08:50:39 sp Syntax colorizing updates and cleanups,
 * general code reorganizations
 * 
 * Revision 1.22 1999/03/13 00:09:07 sp Console updates, uncomment removed cos
 * it's too buggy, cvs log tags added
 * 
 * Revision 1.21 1999/03/12 23:51:00 sp Console updates, uncomment removed cos
 * it's too buggy, cvs log tags added
 */
