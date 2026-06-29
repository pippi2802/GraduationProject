package edu.penn.rtg.csa.dmpr;

import java.io.*;

import javax.xml.parsers.*;

import org.w3c.dom.*;
import org.xml.sax.SAXException;

import edu.penn.rtg.csa.dmpr.Component;
import edu.penn.rtg.csa.dmpr.Task;

/**
 * Class XMLInterpreter4CAMPR
 * This class parse the input xml file to the component tree and return the tree's root.
 * JDK version used: <JDK1.7>
 * @author Meng Xu
 * Create Date: 4/12/2013 
 *
 */

public class XMLInterpreter4DMPR {
	
	private String inputFilename;
	private Component rootComponent;
	private Document doc;
	
	

	public XMLInterpreter4DMPR(String inputFilename) {
		super();
		this.inputFilename = inputFilename;
		
	}

	public boolean parseFile(){
		try{
			doc = DocumentBuilderFactory.newInstance().newDocumentBuilder().parse(new File(inputFilename));
			Node rootNode = doc.getDocumentElement();
			if(rootNode.getNodeName().equalsIgnoreCase("system")){
				parseNode(rootNode, null);
			}else{
				System.err.println("The root component is not <system>");
				return false;
			}		
		}  catch (FactoryConfigurationError e) {
			System.err.println("DocumentBuilderFactory Configuration error:"+e.getMessage());
			//e.printStackTrace();
			return false;
		} catch (ParserConfigurationException e) {
			//e.printStackTrace();
			System.err.println("Parser Configuration error:"+e.getMessage());
			return false;
		} catch (SAXException e) {
			System.err.println("XML error:"+e.getMessage());
			//e.printStackTrace();
			return false;
		} catch (IOException e) {
			if( e instanceof FileNotFoundException) {
				System.err.println("Input file "+inputFilename+" is not founded");
			}
			else
			{
				System.err.println("I/O error:"+e.getMessage());
			}
			//e.printStackTrace();
			return false;
		} catch (Exception e) {
			if(e instanceof NumberFormatException) {
				System.err.println("CARTS XML tag value is not number:"+e.getMessage());
			}
			else
			{
				System.err.println("CARTS XML structure error:"+e.getMessage());
			}
			e.printStackTrace();
			return false;
		}
		
		return true;
	}

	/*
	 * Function parseNode
	 * Parse each node recusively including the leaf node 
	 */
	private void parseNode(Node node, Component parentComponent){
		if(parentComponent == null){
			NamedNodeMap attributes = node.getAttributes();
			String schedulingPolicy = node.getAttributes().getNamedItem("os_scheduler").getNodeValue();		
			String period = "0";
			if(node.getAttributes().getNamedItem("period") == null){
				String period_min = node.getAttributes().getNamedItem("min_period").getNodeValue();
				String period_max = node.getAttributes().getNamedItem("max_period").getNodeValue();
				if(period_min.equals(period_max)){
					period = period_min;
				}else{
					System.err.println("NOT Support a range of period for a component! min_period must equal max_period");
					System.exit(1);
				}
			}else{
				period = node.getAttributes().getNamedItem("period").getNodeValue();
			}
			this.rootComponent = new Component("system", schedulingPolicy, period, null,true);
			this.rootComponent.setComponentFilename(this.inputFilename);
			
			//Now parse its child node recursively
			NodeList childNodes = node.getChildNodes();
			for(int i=0; i<childNodes.getLength(); i++){
				this.parseNode(childNodes.item(i), this.rootComponent);
			}
		}
		
		if(parentComponent != null && node.getNodeName().equals("component")){ //non-root component
			
			String name = node.getAttributes().getNamedItem("name").getNodeValue();
			String schedulingPolicy = node.getAttributes().getNamedItem("scheduler").getNodeValue();
			String period = "0";
			if(node.getAttributes().getNamedItem("period") == null){
				String period_min = node.getAttributes().getNamedItem("min_period").getNodeValue();
				String period_max = node.getAttributes().getNamedItem("max_period").getNodeValue();
				if(period_min.equals(period_max)){
					period = period_min;
				}else{
					System.err.println("NOT Support a range of period for a component! min_period must equal max_period");
					System.exit(1);
				}
			}else{
				period = node.getAttributes().getNamedItem("period").getNodeValue();
			}
			Component currentComponent = new Component(name,schedulingPolicy,period,parentComponent,false);
			currentComponent.setComponentFilename(this.inputFilename);
			parentComponent.addChildComponent(currentComponent);
			
			//now compute its child components recursively
			NodeList childNodes = node.getChildNodes();
			for(int i=0; i< childNodes.getLength(); i++){
				this.parseNode(childNodes.item(i), currentComponent);
			}
		}
		
		if(parentComponent != null && node.getNodeName().equals("task")){ //task
			String name = node.getAttributes().getNamedItem("name").getNodeValue();
			String period = node.getAttributes().getNamedItem("p").getNodeValue();
			String deadline = node.getAttributes().getNamedItem("d").getNodeValue();
			String exe = node.getAttributes().getNamedItem("e").getNodeValue();
			String delta_rel = "0", delta_sch = "0", delta_crpmd = "0", delta_cxs = "0";
			if(node.getAttributes().getNamedItem("delta_rel") != null)
				delta_rel= node.getAttributes().getNamedItem("delta_rel").getNodeValue();
			if(node.getAttributes().getNamedItem("delta_sch") != null) 
				delta_sch = node.getAttributes().getNamedItem("delta_sch").getNodeValue();
			if(node.getAttributes().getNamedItem("delta_crpmd") != null)
				delta_crpmd = node.getAttributes().getNamedItem("delta_crpmd").getNodeValue();
			if(node.getAttributes().getNamedItem("delta_cxs") != null)
				delta_cxs = node.getAttributes().getNamedItem("delta_cxs").getNodeValue();
			Task currentTask = new Task(name, period,deadline, exe, delta_rel,delta_sch,delta_cxs,delta_crpmd);
			parentComponent.addTask(currentTask);
		}
	}


	/**
	 * @param args
	 */
	public static void main(String[] args) {
		// TODO Auto-generated method stub

	}





	
	//////////Get and Set Method///////////////////////////


	public String getInputFilename() {
		return inputFilename;
	}






	public void setInputFilename(String inputFilename) {
		this.inputFilename = inputFilename;
	}






	public Component getRootComponent() {
		return rootComponent;
	}






	public void setRootComponent(Component rootComponent) {
		this.rootComponent = rootComponent;
	}






	public Document getDoc() {
		return doc;
	}


	public void setDoc(Document doc) {
		this.doc = doc;
	}

}
