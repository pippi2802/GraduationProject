/* This program is free software; you can redistribute it and/or
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

//UtilS.java - contains convenience methods used by the main program
//(C)2000-2001 Mark Beynon
//mark@jpedit.co.uk
//http://www.jpedit.co.uk
package com.utils;

import java.awt.*;
import java.awt.event.*;

import javax.swing.JOptionPane;
import javax.swing.JTextPane;

import java.io.File;
import java.io.IOException;
import java.io.FileInputStream;
import java.io.BufferedInputStream;
import java.io.BufferedWriter;
import java.io.FileWriter;

import javax.swing.text.DefaultStyledDocument;

import java.util.StringTokenizer;
import java.util.Vector;

import java.util.Calendar;
import java.util.Date;
import com.wildcrest.j2textprinter.*;
//import com.wildcrest.*;
import com.jpe.jpe;
import com.jpe.Constants;

public class Utils implements ActionListener, Constants {

	private static jpe win;
	private static J2TextPrinter printer = new J2TextPrinter();
	private static String fileSep = System.getProperty("file.separator");
	private static DefaultStyledDocument doc = new DefaultStyledDocument();
	private static final String errorLog = new String("Docs" + fileSep
			+ "errorlog" + fileSep + "errorlog.txt");

	public Utils() {
		super();
	}

	public static void setParent(jpe instance) {
		win = instance;
	}

	public static String getFileName(String s) {
		return new File(s).getName().toString();
	}

	public static boolean isReadOnly(String f) {
		File file = new File(f);
		if (!file.canWrite())
			return true;
		else
			return false;
	}

	public static void writeErrorLog(String s) {
		BufferedWriter out;
		try {
			File errorlog = new File(errorLog);
			errorlog.createNewFile();
			out = new BufferedWriter(new FileWriter(errorlog.getPath(), true));
			out.write(new Date().toString() + " " + s + "\n");
			out.close();
		} catch (IOException ex) {
			userMessage("Error",
					"An error has occured writing the error log!.", 1);
		}
	}

	public static String replaceCharInString(String s, char search, char replace) {
		s.trim();
		char[] Char = s.toCharArray();

		for (int i = 0; i < s.length(); i++) {
			if (Char[i] == search) {
				Char[i] = replace;

			}
		}
		String t = new String(Char.toString());
		return t;

	}

	public static String splitOnToken(String s, String token) {
		Vector v = new Vector();

		StringTokenizer st = new StringTokenizer(s, token);

		while (st.hasMoreTokens()) {
			String r = st.nextToken();
			StringBuffer temp = new StringBuffer(r);
			// temp.deleteCharAt(0);

			v.add(temp.toString() + "<br>&nbsp;");
		}

		String vs = v.toString();

		return vs;
	}

	public static boolean isImage(String s) {
		if ((s.endsWith(".gif")) || (s.endsWith(".jpg"))
				|| (s.endsWith(".GIF")) || (s.endsWith(".JPG")))
			return true;
		else
			return false;
	}

	public static boolean setDefaults() {
		String dialogmessage = "<HTML><font face = arial style='font-size:11pt;font-weight:normal' color='000000'>"
				+ "Restore Defaults?" + "</HTML>";

		JOptionPane jop = new JOptionPane();
		jop.setFont(SYSTEM_FONT);

		int value = jop.showConfirmDialog(win, dialogmessage, "Restore?",
				jop.YES_NO_CANCEL_OPTION);

		switch (value) {
		case JOptionPane.YES_OPTION:
			return win.restoreDefaults();

		case JOptionPane.NO_OPTION:
			return false;

		case JOptionPane.CANCEL_OPTION:
		default:

			return false;
		}

	}

	public static String comboDialog(String title, String message, String[] ints) {

		String dialogmessage = "<HTML><font face = arial style='font-size:11pt;font-weight:normal' color='000000'>"
				+ message + "</HTML>";

		JOptionPane jop = new JOptionPane();
		jop.setFont(SYSTEM_FONT);

		String s = (String) jop.showInputDialog((win), dialogmessage, title,
				jop.QUESTION_MESSAGE, null, ints, ints[0]);
		return s;
	}

	public static File getRoot(File f) {
		// File f = new File( System.getProperty( "user.dir" ) );
		while (f.getParent() != null) {
			f = new File(f.getParent());
		}
		return f;
	}

	public static boolean hasBlanks(String s) {
		s.trim();
		char[] Char = s.toCharArray();
		for (int i = 0; i < s.length(); i++) {
			if (Char[i] == ' ') {
				return true;
			}
		}
		return false;
	}

	public static boolean isOSRoot(String s) {
		String os = System.getProperty("os.name");

		if ((os.startsWith("Win")) && (s.length() < 3)) {
			return true;
		}

		else if ((os.startsWith("Unix")) || (os.startsWith("Linux"))
				|| (os.startsWith("Mac")) && (s.length() < 1)) {
			return true;
		}

		return false;
	}

	public static boolean okToAbandon(boolean dirty, boolean readOnly,
			String currFileName, String untitled) {

		JOptionPane jop = new JOptionPane();
		jop.setFont(SYSTEM_FONT);
		String s;

		if (!dirty) {
			return true;
		}

		if (dirty && readOnly) {
			return true;
		}

		if (currFileName == null) {
			s = untitled;
		} else
			s = new File(currFileName).getName().toString();

		String dialogmessage = "<HTML><font face = arial style='font-size:11pt;font-weight:normal' color='000000'>"
				+ "Save " + s + "?</HTML>";

		int value = jop.showConfirmDialog(win, dialogmessage, "Save file?",
				jop.YES_NO_CANCEL_OPTION);

		switch (value) {
		case JOptionPane.YES_OPTION:
			return win.save();
		case JOptionPane.NO_OPTION:
			return true;
		case JOptionPane.CANCEL_OPTION:
		default:
			return false;
		}
	}

	public static String createWhiteSpace(int len) {
		return createWhiteSpace(len, 0);
	}

	public static String createWhiteSpace(int len, int tabSize) {
		StringBuffer buf = new StringBuffer();

		if (tabSize == 0) {
			while (len-- > 0)
				buf.append(' ');
		} else {
			int count = len / tabSize;
			while (count-- > 0)
				buf.append('\t');

			count = len % tabSize;
			while (count-- > 0)
				buf.append(' ');
		}

		return buf.toString();
	}

	/**
	 * Returns the number of leading white space characters in the specified
	 * string.
	 * 
	 * @param str
	 *            The string
	 */

	public static int getLeadingWhiteSpace(String str) {
		int whitespace = 0;
		loop: for (; whitespace < str.length();) {
			switch (str.charAt(whitespace)) {
			case ' ':
			case '\t':
				whitespace++;
				break;
			default:
				break loop;
			}
		}
		return whitespace;
	}

	public static int getLeadingWhiteSpaceWidth(String str, int tabSize) {
		int whitespace = 0;
		loop: for (int i = 0; i < str.length(); i++) {
			switch (str.charAt(i)) {
			case ' ':
				whitespace++;
				break;
			case '\t':
				whitespace += (tabSize - whitespace % tabSize);
				break;
			default:
				break loop;
			}
		}
		return whitespace;
	}

	public static boolean okToQuit(boolean[] dirty, boolean[] readOnly) {
		String dialogmessage = "<HTML><font face = arial style='font-size:11pt;font-weight:normal' color='000000'>"
				+ "Save unsaved Documents?" + "</HTML>";

		JOptionPane jop = new JOptionPane();
		jop.setFont(SYSTEM_FONT);

		File f;
		String s;
		boolean save = false;

		try {
			for (int i = 0; i < win.tabCount(); i++) {
				if ((dirty[i]) && (!readOnly[i])) {
					save = true;
				}
			}

		} catch (Exception e) {
			System.out.println(e.getMessage());
		}

		if (save) {
			int value = jop.showConfirmDialog(win, dialogmessage,
					"Save Documents?", jop.YES_NO_CANCEL_OPTION);

			switch (value) {
			case JOptionPane.YES_OPTION:
				return win.saveAll();

			case JOptionPane.NO_OPTION:
				return true;

			case JOptionPane.CANCEL_OPTION:
			default:

				return false;
			}
		}

		return true;

	}

	public static void getDate() {
		Calendar c = Calendar.getInstance();
		win.insert(c.toString());
	}

	public static void getTime() {
		Date date = new Date();

		date = Calendar.getInstance().getTime();

		win.insert(date.toString());

	}

	public static void ChangeCase(String type) {
		String select = win.getSelectedText();

		if (type == "Upper")
			win.ReplaceSelection(select.toUpperCase());
		else if (type == "Lower")
			win.ReplaceSelection(select.toLowerCase());
		else
			win.ReplaceSelection(select.toLowerCase());

		win.JpeRequestFocus();
	}

	public static void setHtmlComment() {
		String start = "<!-- ";
		String end = " -->";

		String select = win.getSelectedText();
		if (select == null) {

			win.ReplaceSelection(start + end);
		} else {
			win.ReplaceSelection(start + select + end);
		}

		win.JpeRequestFocus();
	}

	public static void setJavaComment2() {
		String start = "/*" + "\n";
		String end = "\n" + "*/";

		String select = win.getSelectedText();
		if (select == null) {
			win.ReplaceSelection(start + end);
		} else {
			win.ReplaceSelection(start + select + end);
		}

		win.JpeRequestFocus();
	}

	public static String splitOnToken2(String s, String token) {

		StringBuffer sb = new StringBuffer();

		StringTokenizer st = new StringTokenizer(s, token, false);

		while (st.hasMoreTokens()) {
			String r = st.nextToken();

			sb.append("// " + r + "\n");

		}

		return sb.toString();
	}

	public static boolean okToOverwrite(String currFileName, File currFileType) {
		String dialogmessage = "<HTML><font face = arial style='font-size:11pt;font-weight:normal' color='000000'>"
				+ "Overwrite " + "</HTML>";
		String titlemessage = "<HTML><font face = arial style='font-size:11pt;font-weight:normal' color='000000'>"
				+ "Confirm Save" + "</HTML>";

		JOptionPane jop = new JOptionPane();
		jop.setFont(SYSTEM_FONT);

		if (currFileName == null) {
			return win.saveAsFile();
		}

		File file = new File(currFileName);
		if ((file.exists()) && (!file.equals(currFileType))) {
			if (jop.YES_OPTION == jop.showConfirmDialog(win, dialogmessage
					+ currFileName, titlemessage, JOptionPane.YES_NO_OPTION,
					JOptionPane.WARNING_MESSAGE))
				return true;
		} else if ((file.exists()) && (file.equals(currFileType))) {
			return true;
		} else {
			return true;
		}

		win.setcurrFileName(null);
		return false;
	}

	public static boolean genericConfirm(String dialogmessage,
			String titlemessage) {
		dialogmessage = "<HTML><font face = arial style='font-size:11pt;font-weight:normal' color='000000'>"
				+ dialogmessage + "</HTML>";

		JOptionPane jop = new JOptionPane();
		jop.setFont(SYSTEM_FONT);

		int value = jop.showConfirmDialog(win, dialogmessage, titlemessage,
				jop.YES_NO_OPTION, JOptionPane.WARNING_MESSAGE);

		switch (value) {
		case JOptionPane.YES_OPTION:
			return true;

		case JOptionPane.NO_OPTION:
			return false;
		}

		return false;

	}

	public static Font tokenisefont(String s) {

		StringTokenizer fontSt = new StringTokenizer(s, ":", false);

		String fontName = fontSt.nextToken();
		int fontStyle = Integer.parseInt(fontSt.nextToken());
		int fontSize = Integer.parseInt(fontSt.nextToken());

		Font f = new Font(fontName, fontStyle, fontSize);

		return f;
	}

	public static String getDocs(String doc) {
		String s = new String();
		try {
			// Read from the specified file
			File f = new File(doc);
			if (f.exists()) {
				BufferedInputStream in = new BufferedInputStream(
						new FileInputStream(f));
				byte[] b = new byte[in.available()];
				in.read(b, 0, b.length);
				s = (new String(b, 0, b.length));
				in.close();
			} else
				writeErrorLog("Error reading Docs");
		} catch (IOException ex) {
			System.out.println("Error reading Docs folder");
		}
		return s;
	}

	public static void userMessage(String title, String message, int type) {
		JOptionPane jop = new JOptionPane();
		jop.setFont(new Font("Arial", 0, 11));

		String dialogtitle = title;
		String dialogmessage = "<HTML><font face = arial style='font-size:12pt;font-weight:normal' color='000000'>"
				+ message + "</HTML>";
		int dialogtype = 0;
		if (type == 1) {
			dialogtype = jop.WARNING_MESSAGE;

		} else {
			dialogtype = jop.INFORMATION_MESSAGE;
		}

		jop.showMessageDialog((jpe) null, dialogmessage, dialogtitle,
				dialogtype);
	}

	public static void openDefBrowser(String s) {

		try {
			Runtime.getRuntime().exec(
					"rundll32 url.dll,FileProtocolHandler " + s);
		}
		// If the system is not windows, exception will be thrown and
		// accordingly open it in the
		// Netscape browser
		catch (IOException eIO) {
			try {
				Runtime.getRuntime().exec("Netscape.exe " + s);
			} catch (IOException eIOExcp) {

				try {
					Runtime.getRuntime().exec("Iexplore.exe " + s);
				} catch (IOException ieIOExcp) {
				}

			}
		}
		win.repaint();
	}

	public static String convertEOLs(String s) {
		char gap = ' ';
		char[] Char = s.toCharArray();
		for (int i = 0; i < s.length(); i++) {
			if ((Char[i] == '\n') || (Char[i] == '\r') || (Char[i] == '\t')) {
				Char[i] = gap;
			}
		}
		s = new String(Char);
		return s;
	}

	public static void centerComponent(Component compo) {
		compo.setLocation(new Point((getScreenDimension().width - compo
				.getSize().width) / 2, (getScreenDimension().height - compo
				.getSize().height) / 2));
	}

	public static Dimension getScreenDimension() {
		return Toolkit.getDefaultToolkit().getScreenSize();
	}

	public static void Print(String s) {

		JTextPane pane = new JTextPane(doc);

		printer.setPane(pane);
		pane.setText(s);
		printer.setCenterFooter("Page 1 of " + printer.getNumberOfPages());
		printer.setLeftHeader("JPE - Java Programmers Editor");
		printer.setRightHeader("Contact : mark@jpedit.co.uk");
		printer.print();
		win.repaint();
	}

	public static void PrintPreview(String s) {

		JTextPane pane = new JTextPane(doc);
		pane.setText(s);
		printer.setPane(pane);
		printer.showPrintPreviewDialog(win);
		win.repaint();
	}

	public static void PageSetupa() {
		printer.setCenterFooter("Page ### of " + printer.getNumberOfPages());
		printer.setLeftHeader("JPE - Java Programmers Editor");
		printer.setRightHeader("Contact : mark@jpedit.co.uk");

		J2TPPageSetupDialog J2TPPageSetupDialog1 = new J2TPPageSetupDialog(
				printer);
		J2TPPageSetupDialog1.setModal(true);
		J2TPPageSetupDialog1.setTitle("JPE Advanced Page Setup");
		J2TPPageSetupDialog1.show();
		win.repaint();
	}

	public static void PageSetupb() {
		printer.showPageSetupDialog();
		win.repaint();
	}

	public void actionPerformed(ActionEvent e) {

	}

}
