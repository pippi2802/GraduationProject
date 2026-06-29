package edu.penn.rtg.schedulingapp.input.treeGUI.dialog;

import java.util.regex.Pattern;
import javax.swing.JTextField;
import javax.swing.text.AttributeSet;
import javax.swing.text.BadLocationException;
import javax.swing.text.Document;
import javax.swing.text.PlainDocument;

@SuppressWarnings("serial")
class NumericTextField extends JTextField {

	@Override
	protected Document createDefaultModel() {
		return new NumericDocument();
	}

	private static class NumericDocument extends PlainDocument {
		// The regular expression to match input against (zero or more digits)
		private final static Pattern DIGITS = Pattern.compile("[0-9\\.]+");

		@Override
		public void insertString(int offs, String str, AttributeSet a)
				throws BadLocationException {
			// Only insert the text if it matches the regular expression
			if (str != null && DIGITS.matcher(str).matches()) {
				super.insertString(offs, str, a);
			}
		}
	}
}
