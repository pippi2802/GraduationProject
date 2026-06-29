package edu.penn.rtg.schedulingapp.input.treeGUI;

import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;

import javax.swing.JMenuItem;
import javax.swing.JPopupMenu;
import edu.penn.rtg.schedulingapp.TreeComponent;

/**
 * ComponentMenu handles the pop up menu when the user clicks on a Scheduling
 * Component in the Tree UI
 */
@SuppressWarnings("serial")
public class ComponentMenu extends JPopupMenu implements ActionListener {
	private final String addCom="Add Component";
	private final String addTask="Add Task";
	private final String delCom="Remove Component";
	private final String edtCom="Edit Component Data";
	private final String comPRM="Compute PRM interface";
	private final String comEDP="Compute EDP interface";
	private final String comEQV="Compute EQV interface";
	
	private final String comMPR="Compute MPR interface";
	private final String comDMPR="Compute DMPR interface";
	private final String comCADMPR_TASKCENTRIC = "Compute CADMPR_TASKCENTRIC interface";
	private final String comCADMPR_MODELCENTRIC = "Compute CAMPR_MODELCENTRIC interface";
	private final String comCADMPR_HYBRID = "Compute CADMPR_HYBRID interface";
	

	private final String drawGraph="SBF/DBF";
	CartsTree m_treeRef;
	JMenuItem menuGraph;
	public ComponentMenu(CartsTree tree) {
		m_treeRef = tree;
		JMenuItem menuItem;
		menuItem = new JMenuItem(addCom);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(addTask);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(delCom);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(edtCom);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(comPRM);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(comEDP);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(comEQV);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(comMPR);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(comDMPR);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(comCADMPR_TASKCENTRIC);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(comCADMPR_MODELCENTRIC);
		menuItem.addActionListener(this);
		add(menuItem);
		menuItem = new JMenuItem(comCADMPR_HYBRID);
		menuItem.addActionListener(this);
		add(menuItem);
		
		
		menuGraph = new JMenuItem(drawGraph);
		menuGraph.addActionListener(this);
		add(menuGraph);


	}
	public void setCom(TreeComponent comp){
		if(comp.isProcessed()){
			String resourceModel = comp.getResourceModel();
			if(resourceModel.equalsIgnoreCase("EQV")||
					resourceModel.equalsIgnoreCase("MPR") ||
					resourceModel.equalsIgnoreCase("DMPR") || 
					resourceModel.equalsIgnoreCase("CADMPR_TASKCENTRIC") ||
					resourceModel.equalsIgnoreCase("CADMPR_MODELCENTRIC") ||
					resourceModel.equalsIgnoreCase("CADMPR_HYBRID")) { //xm: also exclude CADMPR*
				menuGraph.setEnabled(false);
			}else if(resourceModel.equalsIgnoreCase("PRM") || resourceModel.equalsIgnoreCase("EDP")){
				if(comp.getSchCom().getAlgorithm().equalsIgnoreCase("EDF") 
						|| comp.getSchCom().getAlgorithm().equalsIgnoreCase("DM")
						|| comp.getSchCom().getAlgorithm().equalsIgnoreCase("RM")){
					menuGraph.setEnabled(true);
				}else{
					menuGraph.setEnabled(false);
				}
			}else{
				menuGraph.setEnabled(false);
			}
			
		}else{
			menuGraph.setEnabled(false);
		}
	}

	public void setCom(TreeComponent comp, String resourceModel)
	{
		/**
		 * Display the SBF/DBF option only when the selected component has been
		 * processed
		 */
		if (comp.isProcessed()) {
			if(!(resourceModel.equalsIgnoreCase("EQV")||
					resourceModel.equalsIgnoreCase("MPR")) ||
					resourceModel.equalsIgnoreCase("DMPR") || 
					resourceModel.equalsIgnoreCase("CADMPR_TASKCENTRIC") ||
					resourceModel.equalsIgnoreCase("CADMPR_MODELCENTRIC") ||
					resourceModel.equalsIgnoreCase("CADMPR_HYBRID")) { //xm: also exclude CADMPR*
				menuGraph.setEnabled(true);
			}else{
				menuGraph.setEnabled(false);
			}
		}else{
			menuGraph.setEnabled(false);
			
		}
		
	}
	
	public void setCom(boolean bool){
		menuGraph.setEnabled(bool);
	}
	
	@Override
	public void actionPerformed(ActionEvent e) {
		JMenuItem source = (JMenuItem) (e.getSource());
		if (source.getText().equals(addCom)) {
			m_treeRef.addCompClicked();
		} else if (source.getText().equals(delCom)) {
			m_treeRef.removeCompClicked();
		} else if (source.getText().equals(addTask)) {
			m_treeRef.addTaskClicked();
		} else if (source.getText().equals(edtCom)) {
			m_treeRef.editCompClicked();
		} else if (source.getText().equals(comPRM)) {
			m_treeRef.processAlgo("PRM");
		} else if (source.getText().equals(comEDP)) {
			m_treeRef.processAlgo("EDP");
		} else if (source.getText().equals(comEQV)) {
			m_treeRef.processAlgo("EQV");
		} else if (source.getText().equals(comMPR)) {
			m_treeRef.processAlgo2("MPR");
		} else if (source.getText().equals(comDMPR)) {
			m_treeRef.processAlgo2("DMPR");
		} else if (source.getText().equals(comCADMPR_TASKCENTRIC)) {
			m_treeRef.processAlgo("CADMPR_TASKCENTRIC");
		} else if (source.getText().equals(comCADMPR_MODELCENTRIC)) {
			m_treeRef.processAlgo2("CADMPR_MODELCENTRIC");
		} else if (source.getText().equals(comCADMPR_HYBRID)) {
			m_treeRef.processAlgo2("CADMPR_HYBRID");
		} else if (source.getText().equals(drawGraph)) {
			m_treeRef.drawGraph();
		}
	}
}
