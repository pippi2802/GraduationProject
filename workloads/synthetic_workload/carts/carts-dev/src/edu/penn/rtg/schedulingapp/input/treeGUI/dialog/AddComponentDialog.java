package edu.penn.rtg.schedulingapp.input.treeGUI.dialog;

import javax.swing.JComboBox;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JDialog;
import javax.swing.JPanel;
import javax.swing.JTextField;

import edu.penn.rtg.schedulingapp.input.treeGUI.CartsTree;
import edu.penn.rtg.schedulingapp.util.UserUtil;
import edu.penn.rtg.schedulingapp.SchComponent;
import edu.penn.rtg.schedulingapp.SchedulingComponent;
import edu.penn.rtg.schedulingapp.TreeComponent;

import java.beans.*;
import java.awt.*;
import java.awt.event.*;

/**
 * AddComponentDialog handles the dialog to add new Scheduling Component to the
 * Scheduling Tree
 */
@SuppressWarnings("serial")
public class AddComponentDialog extends JDialog implements ActionListener,
		PropertyChangeListener {
	private final String labName="Component Name";
	private final String labMin="Min Period";
	private final String labMax="Max Period";
	String[] scheduler = { "DM", "EDF", "gEDF", "hEDF" };
	
	protected CartsTree dialogParent;
	protected TreeComponent rootCom;
	protected JComboBox  schedulerSelect;
	protected JTextField compName , vmips,criticality,subType ;
	protected NumericTextField minPeriod, maxPeriod;
	protected JOptionPane optionPane;

	protected String btnString1 = "OK";
	protected String btnString2 = "Cancel";
	protected String mode;
	protected String prevName;

	public AddComponentDialog(CartsTree parent,TreeComponent root) {
		this.rootCom=root;
		this.mode="ADD";
		this.dialogParent = parent;
		this.setDefaultCloseOperation(DISPOSE_ON_CLOSE);
		String title = "New Component";
		setTitle(title);
		makeInputField();
		postDialogAction();
		pack();
	}
	private void makeInputField()
	{
		String msg="Provide details of the component ";
		String optMsg="----- [Optinal field ] -----";
		JLabel criticalityLabel, schedulerLabel , subTypeLabel;
		JLabel compNameLabel , vmipsLabel, minPeriodLabel, maxPeriodLabel;


		schedulerLabel = new JLabel("Scheduler");
		schedulerSelect = new JComboBox(scheduler);
		JPanel panelScheduler = new JPanel(new GridLayout(1, 2));
		panelScheduler.add(schedulerLabel);
		panelScheduler.add(schedulerSelect);


		compNameLabel = new JLabel(labName);
		compName = new JTextField();
		JPanel panelCompName = new JPanel(new GridLayout(1, 2));
		panelCompName.add(compNameLabel);
		panelCompName.add(compName);


		minPeriodLabel = new JLabel(labMin);
		minPeriod = new NumericTextField();
		JPanel panelMinPeriod = new JPanel(new GridLayout(1, 2));
		panelMinPeriod.add(minPeriodLabel);
		panelMinPeriod.add(minPeriod);

		maxPeriodLabel = new JLabel(labMax);
		maxPeriod = new NumericTextField();
		JPanel panelMaxPeriod = new JPanel(new GridLayout(1, 2));
		panelMaxPeriod.add(maxPeriodLabel);
		panelMaxPeriod.add(maxPeriod);


		criticalityLabel = new JLabel("Criticality");
		criticality = new JTextField();
		JPanel panelCriticality = new JPanel(new GridLayout(1, 2));
		panelCriticality.add(criticalityLabel);
		panelCriticality.add(criticality);

		subTypeLabel = new JLabel("Sub Type");
		subType = new JTextField();
		JPanel panelSubType = new JPanel(new GridLayout(1, 2));
		panelSubType.add(subTypeLabel);
		panelSubType.add(subType);

		vmipsLabel = new JLabel("Vmips");
		vmips = new JTextField();
		JPanel panelVmips = new JPanel(new GridLayout(1, 2));
		panelVmips.add(vmipsLabel);
		panelVmips.add(vmips);


		Object[] array = {msg 
						,panelScheduler
						,panelCompName 
						,panelMinPeriod
						,panelMaxPeriod 
						,optMsg
						,panelCriticality
						,panelSubType
						,panelVmips
						};

		Object[] options = { btnString1, btnString2 };

		optionPane = new JOptionPane(array, JOptionPane.PLAIN_MESSAGE,
				JOptionPane.YES_NO_OPTION, null, options, options[0]);

	}
	private void postDialogAction()
	{

		this.setDefaultCloseOperation(JDialog.DISPOSE_ON_CLOSE);
		this.setLocationRelativeTo(this);
		this.setResizable(false);
		this.setModal(true);



		setContentPane(optionPane);

		// Handle window closing correctly.
		setDefaultCloseOperation(DO_NOTHING_ON_CLOSE);
		addWindowListener(new WindowAdapter() {
			public void windowClosing(WindowEvent we) {
				/*
				 * Instead of directly closing the window, we're going to change
				 * the JOptionPane's value property.
				 */
				optionPane.setValue(new Integer(JOptionPane.CLOSED_OPTION));
			}
		});

		// Ensure the text field always gets the first focus.
		addComponentListener(new ComponentAdapter() {
			public void componentShown(ComponentEvent ce) {
				compName.requestFocusInWindow();
			}
		});

		// Register an event handler that reacts to option pane state changes.
		optionPane.addPropertyChangeListener(this);

	}
	public void actionPerformed(ActionEvent e) {

	}

	/** This method reacts to state changes in the option pane. */
	public void propertyChange(PropertyChangeEvent e) {
		String prop = e.getPropertyName();

		if (isVisible()
				&& (e.getSource() == optionPane)
				&& (JOptionPane.VALUE_PROPERTY.equals(prop) || JOptionPane.INPUT_VALUE_PROPERTY
						.equals(prop))) {
			Object value = optionPane.getValue();

			if (value == JOptionPane.UNINITIALIZED_VALUE) {
				return;
			}

			optionPane.setValue(JOptionPane.UNINITIALIZED_VALUE);

			if (btnString1.equals(value)) {
				clickBtnOk();
			} else {
				this.dispose();
			}
		}
	}
	public void clickBtnOk()
	{
		String schedulerStr = new String((String) schedulerSelect
				.getSelectedItem());
		String nameStr = new String(compName.getText());
		String minStr = new String(minPeriod.getText());
		String maxStr = new String(maxPeriod.getText());
		String criticalityStr = new String(criticality.getText());
		String subTypeStr = new String(subType.getText());
		String vmipsStr = new String(vmips.getText());

		if (nameStr.isEmpty()) {
			UserUtil.showErr(labName+" is emptry!");
			return;
		}
		if(prevName==null || !prevName.equals(nameStr)) {
			if(!rootCom.checkNameRecursive(nameStr) ){
				UserUtil.showErr("Given component name is already existed!");
				return;
			}
		}
		if (minStr.isEmpty()) {
			UserUtil.showErr(labMin+" is emptry!");
			return;
		}
		if (maxStr.isEmpty()) {
			UserUtil.showErr(labMax+" is emptry!");
			return;
		}
		double min = Double.parseDouble(minStr);
		double max = Double.parseDouble(maxStr);

		TreeComponent tc=new TreeComponent(nameStr);
		SchComponent c=tc.getSchCom();
		c.setMinPeriod(min);
		c.setMaxPeriod(max);
		c.setAlgorithm(schedulerStr);
		c.setVmipsStr(vmipsStr);
		c.setSubType(subTypeStr);
		c.setCriticality(criticalityStr);
		if (mode.equals("ADD"))	{
			dialogParent.replyFromAddCompDialog(tc);
		}
		else{
			dialogParent.replyFromEditCompDialog(tc);
		}

		this.dispose();
		
	}
}
