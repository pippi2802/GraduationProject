/*
 * PTokenMarker.java - PTM token marker
 * Copyright (C) 1999 Slava Pestov
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

/**
 * JavaScript token marker.
 * 
 * @author Slava Pestov
 * @version $Id: PTokenMarker.java,v 1.4 2000/01/29 10:12:43 sp Exp $
 */
public class PTokenMarker extends CTokenMarker {
	public PTokenMarker() {
		super(false, false, getKeywords());
	}

	public static KeywordMap getKeywords() {
		if (pKeywords == null) {

			pKeywords = new KeywordMap(true);
			pKeywords.add("function", Token.KEYWORD3);
			pKeywords.add("var", Token.KEYWORD3);
			pKeywords.add("var", Token.KEYWORD3);
			pKeywords.add("else", Token.KEYWORD1);
			pKeywords.add("#else", Token.KEYWORD1);
			pKeywords.add("#elseif", Token.KEYWORD1);
			pKeywords.add("for", Token.KEYWORD1);
			pKeywords.add("#foreach", Token.KEYWORD1);
			pKeywords.add("#endfor", Token.KEYWORD1);
			pKeywords.add("#if", Token.KEYWORD1);
			pKeywords.add("if", Token.KEYWORD1);
			pKeywords.add("#then", Token.KEYWORD1);
			pKeywords.add("then", Token.KEYWORD1);
			pKeywords.add("end", Token.KEYWORD1);
			pKeywords.add("#endif", Token.KEYWORD1);
			pKeywords.add("in", Token.KEYWORD1);
			pKeywords.add("new", Token.KEYWORD1);
			pKeywords.add("return", Token.KEYWORD1);
			pKeywords.add("while", Token.KEYWORD1);
			pKeywords.add("with", Token.KEYWORD1);
			pKeywords.add("break", Token.KEYWORD1);
			pKeywords.add("case", Token.KEYWORD1);
			pKeywords.add("continue", Token.KEYWORD1);
			pKeywords.add("default", Token.KEYWORD1);
			pKeywords.add("false", Token.LABEL);
			pKeywords.add("this", Token.LABEL);
			pKeywords.add("true", Token.LABEL);

			pKeywords.add("A", Token.KEYWORD1);
			pKeywords.add("ABBR", Token.KEYWORD1);
			pKeywords.add("ACRONYM", Token.KEYWORD1);
			pKeywords.add("ADDRESS", Token.KEYWORD1);
			pKeywords.add("APPLET", Token.KEYWORD1);
			pKeywords.add("AREA", Token.KEYWORD1);
			pKeywords.add("B", Token.KEYWORD1);
			pKeywords.add("BASE", Token.KEYWORD1);
			pKeywords.add("BASEFONT", Token.KEYWORD1);
			pKeywords.add("BDO", Token.KEYWORD1);
			pKeywords.add("BGSOUND", Token.KEYWORD1);
			pKeywords.add("BIG", Token.KEYWORD1);
			pKeywords.add("BLINK", Token.KEYWORD1);
			pKeywords.add("BLOCKQUOTE", Token.KEYWORD1);
			pKeywords.add("BODY", Token.KEYWORD1);
			pKeywords.add("BR", Token.KEYWORD1);
			pKeywords.add("BUTTON", Token.KEYWORD1);
			pKeywords.add("CAPTION", Token.KEYWORD1);
			pKeywords.add("CENTER", Token.KEYWORD1);
			pKeywords.add("CITE", Token.KEYWORD1);
			pKeywords.add("CODE", Token.KEYWORD1);
			pKeywords.add("COL", Token.KEYWORD1);
			pKeywords.add("COLGROUP", Token.KEYWORD1);
			pKeywords.add("DD", Token.KEYWORD1);
			pKeywords.add("DEL", Token.KEYWORD1);
			pKeywords.add("DFN", Token.KEYWORD1);
			pKeywords.add("DIR", Token.KEYWORD1);
			pKeywords.add("DIV", Token.KEYWORD1);
			pKeywords.add("DL", Token.KEYWORD1);
			pKeywords.add("DT", Token.KEYWORD1);
			pKeywords.add("EM", Token.KEYWORD1);
			pKeywords.add("EMBED", Token.KEYWORD1);
			pKeywords.add("FIELDSET", Token.KEYWORD1);
			pKeywords.add("FONT", Token.KEYWORD1);
			pKeywords.add("FORM", Token.KEYWORD1);
			pKeywords.add("FRAME", Token.KEYWORD1);
			pKeywords.add("FRAMESET", Token.KEYWORD1);
			pKeywords.add("H1", Token.KEYWORD1);
			pKeywords.add("H2", Token.KEYWORD1);
			pKeywords.add("H3", Token.KEYWORD1);
			pKeywords.add("H4", Token.KEYWORD1);
			pKeywords.add("H5", Token.KEYWORD1);
			pKeywords.add("H6", Token.KEYWORD1);
			pKeywords.add("H1", Token.KEYWORD1);
			pKeywords.add("/H2", Token.KEYWORD1);
			pKeywords.add("/H3", Token.KEYWORD1);
			pKeywords.add("/H4", Token.KEYWORD1);
			pKeywords.add("/H5", Token.KEYWORD1);
			pKeywords.add("/H6", Token.KEYWORD1);
			pKeywords.add("HEAD", Token.KEYWORD1);
			pKeywords.add("HR", Token.KEYWORD1);
			pKeywords.add("HTML", Token.KEYWORD1);
			pKeywords.add("I", Token.KEYWORD1);
			pKeywords.add("IFRAME", Token.KEYWORD1);
			pKeywords.add("ILAYER", Token.KEYWORD1);
			pKeywords.add("IMG", Token.KEYWORD1);
			pKeywords.add("INPUT", Token.KEYWORD1);
			pKeywords.add("INS", Token.KEYWORD1);
			pKeywords.add("ISINDEX", Token.KEYWORD1);
			pKeywords.add("KBD", Token.KEYWORD1);
			pKeywords.add("KEYGEN", Token.KEYWORD1);
			pKeywords.add("LABEL", Token.KEYWORD1);
			pKeywords.add("LAYER", Token.KEYWORD1);
			pKeywords.add("LEGEND", Token.KEYWORD1);
			pKeywords.add("LI", Token.KEYWORD1);
			pKeywords.add("LINK", Token.KEYWORD1);
			pKeywords.add("LISTING", Token.KEYWORD1);
			pKeywords.add("MAP", Token.KEYWORD1);
			pKeywords.add("MENU", Token.KEYWORD1);
			pKeywords.add("META", Token.KEYWORD1);
			pKeywords.add("MULTICOL", Token.KEYWORD1);
			pKeywords.add("NOBR", Token.KEYWORD1);
			pKeywords.add("NOEMBED", Token.KEYWORD1);
			pKeywords.add("NOFRAMES", Token.KEYWORD1);
			pKeywords.add("NOLAYER", Token.KEYWORD1);
			pKeywords.add("NOSCRIPT", Token.KEYWORD1);
			pKeywords.add("OBJECT", Token.KEYWORD1);
			pKeywords.add("OL", Token.KEYWORD1);
			pKeywords.add("OPTGROUP", Token.KEYWORD1);
			pKeywords.add("OPTION", Token.KEYWORD1);
			pKeywords.add("P", Token.KEYWORD1);
			pKeywords.add("PARAM", Token.KEYWORD1);
			pKeywords.add("PLAINTEXT", Token.KEYWORD1);
			pKeywords.add("PRE", Token.KEYWORD1);
			pKeywords.add("Q", Token.KEYWORD1);
			pKeywords.add("S", Token.KEYWORD1);
			pKeywords.add("SAMP", Token.KEYWORD1);
			pKeywords.add("SCRIPT", Token.KEYWORD1);
			pKeywords.add("SELECT", Token.KEYWORD1);
			pKeywords.add("SERVER", Token.KEYWORD1);
			pKeywords.add("SMALL", Token.KEYWORD1);
			pKeywords.add("SOUND", Token.KEYWORD1);
			pKeywords.add("SPACER", Token.KEYWORD1);
			pKeywords.add("SPAN", Token.KEYWORD1);
			pKeywords.add("STRIKE", Token.KEYWORD1);
			pKeywords.add("STRONG", Token.KEYWORD1);
			pKeywords.add("STYLE", Token.KEYWORD1);
			pKeywords.add("SUB", Token.KEYWORD1);
			pKeywords.add("SUP", Token.KEYWORD1);
			pKeywords.add("TBODY", Token.KEYWORD1);
			pKeywords.add("TEXTAREA", Token.KEYWORD1);
			pKeywords.add("TITLE", Token.KEYWORD1);
			pKeywords.add("TT", Token.KEYWORD1);
			pKeywords.add("U", Token.KEYWORD1);
			pKeywords.add("UL", Token.KEYWORD1);
			pKeywords.add("VAR", Token.KEYWORD1);
			pKeywords.add("WBR", Token.KEYWORD1);
			pKeywords.add("XMP", Token.KEYWORD1);

			pKeywords.add("TABLE", Token.KEYWORD2);
			pKeywords.add("TD", Token.KEYWORD2);
			pKeywords.add("TFOOT", Token.KEYWORD2);
			pKeywords.add("TH", Token.KEYWORD2);
			pKeywords.add("THEAD", Token.KEYWORD2);
			pKeywords.add("TR", Token.KEYWORD2);
			pKeywords.add("/TABLE", Token.KEYWORD2);
			pKeywords.add("/TD", Token.KEYWORD2);
			pKeywords.add("/TFOOT", Token.KEYWORD2);
			pKeywords.add("/TH", Token.KEYWORD2);
			pKeywords.add("/THEAD", Token.KEYWORD2);
			pKeywords.add("/TR", Token.KEYWORD2);

			pKeywords.add("ACCESSKEY", Token.KEYWORD2);
			pKeywords.add("&nbsp;", Token.KEYWORD2);
			pKeywords.add("ACTION", Token.KEYWORD2);
			pKeywords.add("ALIGN", Token.KEYWORD2);
			pKeywords.add("ALINK", Token.KEYWORD2);
			pKeywords.add("ALT", Token.KEYWORD2);
			pKeywords.add("BACKGROUND", Token.KEYWORD2);
			pKeywords.add("BALANCE", Token.KEYWORD2);
			pKeywords.add("BEHAVIOR", Token.KEYWORD2);
			pKeywords.add("BGCOLOR", Token.KEYWORD2);
			pKeywords.add("BGPROPERTIES", Token.KEYWORD2);
			pKeywords.add("BORDER", Token.KEYWORD2);
			pKeywords.add("BORDERCOLOR", Token.KEYWORD2);
			pKeywords.add("BORDERCOLORDARK", Token.KEYWORD2);
			pKeywords.add("BORDERCOLORLIGHT", Token.KEYWORD2);
			pKeywords.add("BOTTOMMARGIN", Token.KEYWORD2);
			pKeywords.add("CELLPADDING", Token.KEYWORD2);
			pKeywords.add("CELLSPACING", Token.KEYWORD2);
			pKeywords.add("CHECKED", Token.KEYWORD2);
			pKeywords.add("CLASS", Token.KEYWORD2);
			pKeywords.add("CLASSID", Token.KEYWORD2);
			pKeywords.add("CLEAR", Token.KEYWORD2);
			pKeywords.add("CODE", Token.KEYWORD2);
			pKeywords.add("CODEBASE", Token.KEYWORD2);
			pKeywords.add("CODETYPE", Token.KEYWORD2);
			pKeywords.add("COLOR", Token.KEYWORD2);
			pKeywords.add("COLS", Token.KEYWORD2);
			pKeywords.add("COLSPAN", Token.KEYWORD2);
			pKeywords.add("COMPACT", Token.KEYWORD2);
			pKeywords.add("CONTENT", Token.KEYWORD2);
			pKeywords.add("CONTROLS", Token.KEYWORD2);
			pKeywords.add("COORDS", Token.KEYWORD2);
			pKeywords.add("DATA", Token.KEYWORD2);
			pKeywords.add("DATAFLD", Token.KEYWORD2);
			pKeywords.add("DATAFORMATAS", Token.KEYWORD2);
			pKeywords.add("DATASRC", Token.KEYWORD2);
			pKeywords.add("DIRECTION", Token.KEYWORD2);
			pKeywords.add("DISABLED", Token.KEYWORD2);
			pKeywords.add("DYNSRC", Token.KEYWORD2);
			pKeywords.add("ENCTYPE", Token.KEYWORD2);
			pKeywords.add("EVENT", Token.KEYWORD2);
			pKeywords.add("FACE", Token.KEYWORD2);
			pKeywords.add("FOR", Token.KEYWORD2);
			pKeywords.add("FRAME", Token.KEYWORD2);
			pKeywords.add("FRAMEBORDER", Token.KEYWORD2);
			pKeywords.add("FRAMESPACING", Token.KEYWORD2);
			pKeywords.add("HEIGHT", Token.KEYWORD2);
			pKeywords.add("HIDDEN", Token.KEYWORD2);
			pKeywords.add("HREF", Token.KEYWORD2);
			pKeywords.add("HSPACE", Token.KEYWORD2);
			pKeywords.add("HTTP-EQUIV", Token.KEYWORD2);
			pKeywords.add("ID", Token.KEYWORD2);
			pKeywords.add("ISMAP", Token.KEYWORD2);
			pKeywords.add("LANG", Token.KEYWORD2);
			pKeywords.add("LANGUAGE", Token.KEYWORD2);
			pKeywords.add("LEFTMARGIN", Token.KEYWORD2);
			pKeywords.add("LINK", Token.KEYWORD2);
			pKeywords.add("LOOP", Token.KEYWORD2);
			pKeywords.add("LOWSRC", Token.KEYWORD2);
			pKeywords.add("MARGINHEIGHT", Token.KEYWORD2);
			pKeywords.add("MARGINWIDTH", Token.KEYWORD2);
			pKeywords.add("MAXLENGTH", Token.KEYWORD2);
			pKeywords.add("MAYSCRIPT", Token.KEYWORD2);
			pKeywords.add("METHOD", Token.KEYWORD2);
			pKeywords.add("METHODS", Token.KEYWORD2);
			pKeywords.add("MULTIPLE", Token.KEYWORD2);
			pKeywords.add("NAME", Token.KEYWORD2);
			pKeywords.add("NOHREF", Token.KEYWORD2);
			pKeywords.add("NORESIZE", Token.KEYWORD2);
			pKeywords.add("NOSHADE", Token.KEYWORD2);
			pKeywords.add("NOWRAP", Token.KEYWORD2);
			pKeywords.add("PALETTE", Token.KEYWORD2);
			pKeywords.add("P", Token.KEYWORD2);
			pKeywords.add("/P", Token.KEYWORD2);
			pKeywords.add("PLUGINSPAGE", Token.KEYWORD2);
			pKeywords.add("PUBLIC", Token.KEYWORD2);
			pKeywords.add("READONLY", Token.KEYWORD2);
			pKeywords.add("REL", Token.KEYWORD2);
			pKeywords.add("REV", Token.KEYWORD2);
			pKeywords.add("RIGHTMARGIN", Token.KEYWORD2);
			pKeywords.add("ROWS", Token.KEYWORD2);
			pKeywords.add("ROWSPAN", Token.KEYWORD2);
			pKeywords.add("RULES", Token.KEYWORD2);
			pKeywords.add("SCROLL", Token.KEYWORD2);
			pKeywords.add("SCROLLAMOUNT", Token.KEYWORD2);
			pKeywords.add("SCROLLDELAY", Token.KEYWORD2);
			pKeywords.add("SCROLLING", Token.KEYWORD2);
			pKeywords.add("SELECTED", Token.KEYWORD2);
			pKeywords.add("SHAPE", Token.KEYWORD2);
			pKeywords.add("SIZE", Token.KEYWORD2);
			pKeywords.add("SPAN", Token.KEYWORD2);
			pKeywords.add("SRC", Token.KEYWORD2);
			pKeywords.add("START", Token.KEYWORD2);
			pKeywords.add("STYLE", Token.KEYWORD2);
			pKeywords.add("TABINDEX", Token.KEYWORD2);
			pKeywords.add("TARGET", Token.KEYWORD2);
			pKeywords.add("TEXT", Token.KEYWORD2);
			pKeywords.add("TITLE", Token.KEYWORD2);
			pKeywords.add("TOPMARGIN", Token.KEYWORD2);
			pKeywords.add("TRUESPEED", Token.KEYWORD2);
			pKeywords.add("TYPE", Token.KEYWORD2);
			pKeywords.add("URL", Token.KEYWORD2);
			pKeywords.add("URN", Token.KEYWORD2);
			pKeywords.add("USEMAP", Token.KEYWORD2);
			pKeywords.add("VALIGN", Token.KEYWORD2);
			pKeywords.add("VALUE", Token.KEYWORD2);
			pKeywords.add("VLINK", Token.KEYWORD2);
			pKeywords.add("VOLUME", Token.KEYWORD2);
			pKeywords.add("VRML", Token.KEYWORD2);
			pKeywords.add("VSPACE", Token.KEYWORD2);
			pKeywords.add("WIDTH", Token.KEYWORD2);
			pKeywords.add("WRAP", Token.KEYWORD2);

		}
		return pKeywords;
	}

	// private members
	private static KeywordMap pKeywords;
}

/*
 * ChangeLog: $Log: PTokenMarker.java,v $ Revision 1.4 2000/01/29 10:12:43 sp
 * BeanShell edit mode, bug fixes
 * 
 * Revision 1.3 1999/12/13 03:40:29 sp Bug fixes, syntax is now mostly GPL'd
 * 
 * Revision 1.2 1999/06/05 00:22:58 sp LGPL'd syntax package
 * 
 * Revision 1.1 1999/03/13 09:11:46 sp Syntax code updates, code cleanups
 */
